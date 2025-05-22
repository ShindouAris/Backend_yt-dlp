from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from collections import deque
import uuid
import os
import yt_dlp
import pathlib
from asgiref.sync import sync_to_async as s2a
from asyncio import sleep, create_task
from shutil import rmtree
from contextlib import asynccontextmanager
import datetime
from dotenv import load_dotenv
from get_quality import fetch_format_data, FormatInfo

load_dotenv()

# --- Configuration ---
PROJECT_ROOT = pathlib.Path(__file__).parent
DOWNLOAD_FOLDER = pathlib.Path('downloads')
COOKIE_FILE = pathlib.Path("./cookies.txt")

DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

if COOKIE_FILE.exists():
    cookie_file = COOKIE_FILE
else:
    cookie_file = None

class DownloadResponse(BaseModel):
    message: str
    filename: str | None = None
    download_link: str | None = None
    details: str | None = None
    yt_dlp_output: str | None = None

class FileSession:
    def __init__(self):
        self.sessions = deque()
        self.storage: dict[str, tuple[pathlib.Path, float]] = {}
        self._task = None

    def add_session(self, session_id, file_path: pathlib.Path =None):
        self.sessions.append(session_id)
        if file_path:
            self.storage[session_id] = (file_path, datetime.datetime.utcnow().timestamp())

    def __pop_session(self):
        if self.sessions:
            return self.sessions.popleft()
        return None

    async def auto_delete_file_task(self):
        while True:
            timeout = 300
            await sleep(60)
            expired_sessions = []
            now = datetime.datetime.utcnow().timestamp()

            for session_id, (file_path, created_time) in list(self.storage.items()):
                if now - created_time >= timeout:
                    if file_path.exists():
                        rmtree(file_path)
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                self.sessions.remove(session_id)
                del self.storage[session_id]

    def clear_sessions(self):
        while self.sessions:
            session_id = self.__pop_session()
            file_path = self.storage.get(session_id)
            if file_path and file_path[0].exists():
                rmtree(file_path[0])
                del self.storage[session_id]

    def start(self):
        if self._task is None:
            self._task = create_task(self.auto_delete_file_task())

file_session = FileSession()
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Starts the auto-delete task for files.
    """
    file_session.start()
    yield None
    file_session.clear_sessions()
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                    allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class DownloadRequest(BaseModel):
    url: str
    format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

class FormatRequest(BaseModel):
    url: str

class FormatResponse(BaseModel):
    name: str
    formats: list[FormatInfo]

def generate_uuid():
    return str(uuid.uuid4())

def run_yt_dlp_download(url: str, format_option: str, output: pathlib.Path):
    """
    Runs yt-dlp in a subprocess.
    This function is designed to be run in a background task or awaited.
    Returns a dictionary with results or raises an exception.
    """
    ydl_opts = {
        'format': format_option,
        'outtmpl': {
            'default': str(output) + '/%(title)s.%(ext)s',
        },
        'keepvideo': False,
        'noplaylist': False,
        'noprogress': True,
        'ignoreerrors': True,
        'quiet': True,
        'verbose': False,
        'no_warnings': True,
        'simulate': False,
        'extract_flat': False,
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([yt_dlp.utils.sanitize_url(url)])
            return {
                "success": True,
                "file_location": output,
            }
        except yt_dlp.utils.DownloadError:
            return {
                "success": False,
            }

def get_file_name(url, format_option, output_template):
    ydl_opts = {
        "format": format_option,
        "outtmpl": output_template,
        "quiet": True,
        "simulate": True,
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info_dict)
            print(f"Extracted filename: {filename}")
            return filename
        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"Error extracting file name: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def fetch_file(path: pathlib.Path):
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    for file in path.glob("*.mp4"):
        if file.is_file():
            return file.name

@app.post("/get_all_format", response_model=FormatResponse)
async def get_all_formats(request: FormatRequest):

    url = request.url

    if not url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        formats, file_name = await s2a(fetch_format_data)(url, cookiefile=cookie_file)
        if not formats:
            raise HTTPException(status_code=404, detail="Failed to fetch formats")
        return FormatResponse(
            name=file_name,
            formats=formats
        )
    except Exception as e:
        print("An error occurred while fetching formats:", str(e))
        raise HTTPException(status_code=500, detail=f"Error fetching formats: {str(e)}")

@app.post("/download")
async def download_video(request_data: DownloadRequest):
    url = request_data.url
    format_option = request_data.format

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    session_id = generate_uuid()

    output = pathlib.Path(os.path.join(DOWNLOAD_FOLDER / session_id))

    output.mkdir(parents=True, exist_ok=True)
    try:
        result = await s2a(run_yt_dlp_download)(url, format_option, output)

        if result["success"]:
            filename = await s2a(get_file_name)(url, format_option, str(output) + '/%(title)s.%(ext)s')
            file_session.add_session(session_id, output)
            return DownloadResponse(
                message="Download completed",
                filename=filename,
                download_link=f"/files/{session_id}",
                details="File has been downloaded successfully",
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

@app.get("/files/{session_id}")
async def get_downloaded_file(session_id: str):
    file = pathlib.Path(os.path.join(PROJECT_ROOT / DOWNLOAD_FOLDER, session_id))
    for f in file.glob("*.mp4"):
        if f.is_file():
            filename = f.name
            if not os.path.isfile(f):
                raise HTTPException(status_code=404, detail=f"File not found: {file}")
            return FileResponse(path=f, filename=filename, media_type='application/octet-stream')
    raise HTTPException(status_code=404, detail=f"File not found: {file}")

if os.environ.get("KEEP_ALIVE", 'false').lower() == "true":
    @app.get("/")
    async def root():
        return {"message": "Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backendv2:app", host="0.0.0.0", port=8080)