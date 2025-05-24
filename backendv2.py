from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from collections import deque
import uuid
import os
import pathlib
from asgiref.sync import sync_to_async as s2a
from asyncio import sleep, create_task
from shutil import rmtree
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from dotenv import load_dotenv

import yt_dlp
from ytdl_tools import fetch_format_data, run_yt_dlp_download
from geoblock_checker import is_geo_restricted, get_video_id, GeoblockData
from request_class import DownloadRequest, FormatRequest, FormatResponse, DownloadResponse

from logging_utils import LOGGING_CONFIG
from logging import getLogger


load_dotenv()
log = getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).parent
DOWNLOAD_FOLDER = pathlib.Path('downloads')

DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

class FileSession:
    def __init__(self):
        self.sessions = deque()
        self.storage: dict[str, tuple[pathlib.Path, float]] = {}
        self._task = None

    def add_session(self, session_id, file_path: pathlib.Path =None):
        self.sessions.append(session_id)
        if file_path:
            self.storage[session_id] = (file_path, datetime.now(timezone.utc).timestamp())
        log.debug("Added session: %s", session_id)

    def __pop_session(self):
        if self.sessions:
            return self.sessions.popleft()
        return None

    async def auto_delete_file_task(self):
        while True:
            timeout = 300
            await sleep(60)
            expired_sessions = []
            now = datetime.now(timezone.utc).timestamp()

            for session_id, (file_path, created_time) in list(self.storage.items()):
                if now - created_time >= timeout:
                    if file_path.exists():
                        log.debug("Session outdated: %s", session_id)
                        rmtree(file_path)
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                self.sessions.remove(session_id)
                del self.storage[session_id]

    def clear_sessions(self):
        log.debug("Clearing all sessions")
        while self.sessions:
            session_id = self.__pop_session()
            file_path = self.storage.get(session_id)
            if file_path and file_path[0].exists():
                rmtree(file_path[0])
                del self.storage[session_id]

    def start(self):
        if self._task is None:
            self._task = create_task(self.auto_delete_file_task())

def resolve_file_name_from_folder(path: str) -> str:
    """
    Returns the first file name inside the given folder path.
    """
    if not path:
        raise ValueError("Path cannot be empty")
    if not os.path.isdir(path):
        raise ValueError(f"'{path}' is not a directory")

    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    if not files:
        raise FileNotFoundError(f"No files found in folder: {path}")

    return files[0]

def is_valid_uuid4(s: str) -> bool:
    try:
        return str(uuid.UUID(s, version=4)) == s
    except ValueError:
        return False


class BaseApplication(FastAPI):
    def __init__(self):
        super().__init__(lifespan=self.lifespan)
        self.add_api_route("/get_all_format", self.get_all_formats, response_model=FormatResponse, methods=["POST"])
        self.add_api_route("/download", self.download_video, methods=["POST"])
        self.add_api_route("/files/{session_id}", self.get_downloaded_file, methods=["GET"])
        self.add_api_route("/geo_check", self.check_geo_block, methods=["POST"], response_model=GeoblockData)
        self.add_middleware(CORSMiddleware, allow_origins=["https://youtube-downloader-nine-drab.vercel.app", "http://localhost:5173"],
                        allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
        self.add_api_route("/", self.root, methods=["GET", "HEAD"])
        self.file_session = FileSession()
        self.uptime = datetime.now(timezone.utc)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Starts the auto-delete task for files.
        """
        self.file_session.start()
        yield None
        self.file_session.clear_sessions()

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())

    async def check_geo_block(self, request: FormatRequest):

        url = request.url

        if not url.strip():
            raise HTTPException(status_code=400, detail="URL is requied")

        video_id = get_video_id(url)
        GOOGLE_API_V3 = os.environ.get("YOUTUBE_V3_APIKEY", None)
        if GOOGLE_API_V3 is None:
            raise HTTPException(status_code=401, detail="This backend is not configured for geochecking")

        check: GeoblockData = await is_geo_restricted(video_id, GOOGLE_API_V3)

        return check


    async def get_all_formats(self, request: FormatRequest):

        url = request.url

        if not url.strip():
            raise HTTPException(status_code=400, detail="URL is required")

        try:
            formats, file_name = await s2a(fetch_format_data)(url, max_audio=3, cookiefile="./cookie.txt")
            if not formats:
                log.error(f"Fail to load formats for {url}")
                raise HTTPException(status_code=404, detail="No formats found")
            return FormatResponse(
                name=file_name,
                formats=formats
            )
        except Exception as e:
            log.error("An error occurred while fetching formats:", str(e))
            raise HTTPException(status_code=500, detail=f"Error fetching formats: {str(e)}")

    async def download_video(self, request_data: DownloadRequest):
        url = request_data.url
        format_option = request_data.format

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        session_id = self.generate_uuid()

        output = pathlib.Path(os.path.join(DOWNLOAD_FOLDER / session_id))

        output.mkdir(parents=True, exist_ok=True)
        try:
            result = await s2a(run_yt_dlp_download)(url, format_option, output)

            if result["success"]:
                filename = resolve_file_name_from_folder(str(output))
                self.file_session.add_session(session_id, output)
                return DownloadResponse(
                    message="Download completed",
                    filename=filename,
                    download_link=f"/files/{session_id}",
                )
            else:
                return Response(
                    content="Download failed",
                    status_code=500
                )
        except yt_dlp.utils.DownloadError:
            return Response(
                content="Download failed",
                status_code=500,
            )

    async def get_downloaded_file(self, session_id: str):
        if not is_valid_uuid4(session_id):
            raise HTTPException(400, detail="Invalid session ID")

        base_dir = (PROJECT_ROOT / DOWNLOAD_FOLDER).resolve()
        requested_path = (base_dir / session_id).resolve()

        if not str(requested_path).startswith(str(base_dir)):
            raise HTTPException(403, detail="Forbidden path access")

        preferred_extensions = [
            "mp4", "mkv", "webm", "flv", "3gp", "mov", "avi", "ts",
            "m4a", "mp3", "ogg", "opus", "flac", "wav", "aac", "alac", "aiff", "dsf", "pcm",
        ]
        for ext in preferred_extensions:
            for f in requested_path.glob(f"*.{ext}"):
                if f.is_file():
                    return FileResponse(path=f, filename=f.name, media_type='application/octet-stream')

        raise HTTPException(404, detail="No downloadable file found.")
    async def root(self):
        beautiful_format = ""
        for route in self.routes:
            beautiful_format += f"[ [{route.name}] - [{route.methods}] - [{route.path}] ]"
        return {"message": f"Server is running - {beautiful_format} - Last restart: {self.uptime.ctime()}"}

if __name__ == "__main__":
    import uvicorn
    log.info(f"YT-DLP VERSION: {yt_dlp.version.__version__}")
    uvicorn.run(BaseApplication, host="0.0.0.0", port=8000, log_config=LOGGING_CONFIG)