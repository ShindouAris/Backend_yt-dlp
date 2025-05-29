import time
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse, RedirectResponse, HTMLResponse

from collections import deque
import uuid
import os
import pathlib
from asgiref.sync import sync_to_async as s2a
from asyncio import sleep, create_task, TimeoutError as AsyncTimeoutError
from shutil import rmtree
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from dotenv import load_dotenv

import yt_dlp
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from manager.ytdlp_tool.ytdl_tools import fetch_data, run_yt_dlp_download
from manager.geo_utils.geoblock_checker import is_geo_restricted, get_video_id, GeoblockData
from manager.models.request_class import DownloadRequest, FormatRequest, DataResponse, DownloadResponse
from manager.database_utils.r2_storage import R2Storage
from manager.database_utils.url_cache import URLCache
from manager.LRU_cache.format_cache import FormatCache
from manager.configuation.config import *
from manager.turnstiles_authentication.turnstile import Turnstile
from manager.logging.logging_utils import LOGGING_CONFIG
from logging import getLogger

import random


load_dotenv()
log = getLogger(__name__)

rate_limit_cache: Dict[str, list] = {}

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    request_times = rate_limit_cache.get(ip, [])
    request_times = [t for t in request_times if now - t < RATE_WINDOW]
    if len(request_times) >= RATE_LIMIT:
        return True
    request_times.append(now)
    rate_limit_cache[ip] = request_times
    return False

auth_scheme = HTTPBearer(auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if credentials is None or credentials.credentials != SECRET_PRODUCTION_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host
        if is_rate_limited(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
            )
        return await call_next(request)

class FileSession:
    def __init__(self):
        self.sessions = deque()
        self.storage: dict[str, tuple[pathlib.Path, float]] = {}
        self._task = None
        self.r2_storage = R2Storage()
        self.url_cache = URLCache()
        self.format_cache = FormatCache(capacity=1000, expire_seconds=1800)  # 30 minutes expiration
        self._upload_tasks: dict[str, create_task] = {}  # Track upload tasks

    async def _upload_to_r2(self, session_id: str, file_path: pathlib.Path, url: str, format_option: str) -> None:
        """
        Asynchronously upload a file to R2 storage with timeout handling.
        """
        try:
            first_file = resolve_file_name_from_folder(str(file_path))
            full_file_path = file_path / first_file
            object_name = f"{session_id}/{first_file}"

            # Attempt upload with timeout
            upload_success = await s2a(self.r2_storage.upload_file)(str(full_file_path), object_name)
            
            if upload_success:
                # Cache the file information
                self.url_cache.cache_file(
                    url,
                    format_option,
                    {
                        "session_id": session_id,
                        "object_name": object_name,
                        "filename": first_file
                    },
                    FILE_EXPIRE_TIME
                )
                # Delete local file after successful upload
                rmtree(file_path)
                # Store only the filename for reference
                self.storage[session_id] = (pathlib.Path(first_file), datetime.now(timezone.utc).timestamp())
            else:
                # If R2 upload fails, keep local file as fallback
                self.storage[session_id] = (file_path, datetime.now(timezone.utc).timestamp())
                log.warning(f"R2 upload failed for session {session_id}, keeping local file")

        except (AsyncTimeoutError, Exception) as e:
            log.error(f"Error during R2 upload for session {session_id}: {e}")
            # Keep local file as fallback
            self.storage[session_id] = (file_path, datetime.now(timezone.utc).timestamp())
        finally:
            # Clean up the task reference
            if session_id in self._upload_tasks:
                del self._upload_tasks[session_id]

    def add_session(self, session_id, file_path: pathlib.Path = None, url: str = None, format_option: str = None):
        """Add a new session with associated file path"""
        self.sessions.append(session_id)
        if file_path:
            if self.r2_storage.enabled and url and format_option:
                # Create async task for R2 upload
                upload_task = create_task(self._upload_to_r2(session_id, file_path, url, format_option))
                self._upload_tasks[session_id] = upload_task
                # Initially store the local path until upload completes
                self.storage[session_id] = (file_path, datetime.now(timezone.utc).timestamp())
            else:
                # If R2 is not enabled, store locally with full path
                self.storage[session_id] = (file_path, datetime.now(timezone.utc).timestamp())

            log.debug("Added session: %s with storage type: %s", 
                     session_id, 
                     "R2 (uploading)" if self.r2_storage.enabled else "local")

    def __pop_session(self):
        if self.sessions:
            return self.sessions.popleft()
        return None

    async def auto_delete_file_task(self):
        while True:
            await sleep(60)
            expired_sessions = []
            now = datetime.now(timezone.utc).timestamp()

            for session_id, (file_path, created_time) in list(self.storage.items()):
                if now - created_time >= FILE_EXPIRE_TIME:
                    try:
                        # Handle local storage cleanup
                        if not self.r2_storage.enabled:
                            # For local storage, file_path is the full path to the session directory
                            full_path = file_path if isinstance(file_path, pathlib.Path) else DOWNLOAD_FOLDER / session_id
                            if DISABLE_AUTO_CLEANUP:
                                log.debug("Skipping cleanup for local session: %s", session_id)
                                continue
                            if full_path.exists():
                                log.debug("Cleaning up local session: %s", session_id)
                                rmtree(full_path)
                        
                        # Handle R2 storage cleanup
                        elif self.r2_storage.enabled:
                            # For R2 storage, file_path is just the filename
                            filename = file_path.name if isinstance(file_path, pathlib.Path) else file_path
                            object_name = f"{session_id}/{filename}"
                            await s2a(self.r2_storage.delete_file)(object_name)
                        
                        # Handle cache cleanup (both Redis and in-memory)
                        if self.url_cache.enabled:
                            self.url_cache.remove_all_by_session(session_id)
                        
                        expired_sessions.append(session_id)
                        
                    except Exception as e:
                        log.error(f"Error during cleanup for session {session_id}: {e}")

            # Remove expired sessions from tracking
            for session_id in expired_sessions:
                try:
                    self.sessions.remove(session_id)
                    del self.storage[session_id]
                except Exception as e:
                    log.error(f"Error removing session {session_id} from tracking: {e}")

    async def clear_sessions(self):
        """
        Emergency cleanup method to clear all sessions and their associated resources.
        This is important to prevent storage leaks and should be called during shutdown.
        """
        log.info("Emergency cleanup: Clearing all sessions...")
        cleaned = 0
        errors = 0

        # Wait for any pending uploads to complete or timeout
        if self._upload_tasks:
            log.info(f"Waiting for {len(self._upload_tasks)} pending uploads to complete...")
            for session_id, task in self._upload_tasks.items():
                try:
                    await task
                except Exception as e:
                    log.error(f"Error waiting for upload task {session_id}: {e}")

        while self.sessions:
            try:
                session_id = self.__pop_session()
                file_path = self.storage.get(session_id)
                
                if file_path:
                    try:
                        if not self.r2_storage.enabled:
                            if DISABLE_AUTO_CLEANUP:
                                log.debug("Skipping cleanup for local session: %s", session_id)
                                continue
                            full_path = file_path[0] if isinstance(file_path[0], pathlib.Path) else DOWNLOAD_FOLDER / session_id
                            if full_path.exists():
                                log.debug("Cleaning up local session: %s", session_id)
                                rmtree(full_path)

                        elif self.r2_storage.enabled:
                            # For R2 storage, file_path[0] is just the filename
                            filename = file_path[0].name if isinstance(file_path[0], pathlib.Path) else file_path[0]
                            object_name = f"{session_id}/{filename}"
                            await s2a(self.r2_storage.delete_file)(object_name)

                        if self.url_cache.enabled:
                            self.url_cache.remove_all_by_session(session_id)
                        
                        del self.storage[session_id]
                        cleaned += 1
                        
                    except Exception as e:
                        errors += 1
                        log.error(f"Error cleaning up session {session_id}: {e}")
                        
            except Exception as e:
                errors += 1
                log.error(f"Error during session cleanup: {e}")

        log.info("Emergency cleanup completed: %d sessions cleaned, %d errors", cleaned, errors)

        try:
            if DOWNLOAD_FOLDER.exists():
                for session_dir in DOWNLOAD_FOLDER.iterdir():
                    if session_dir.is_dir():
                        try:
                            rmtree(session_dir)
                            log.debug("Cleaned up orphaned session directory: %s", session_dir)
                        except Exception as e:
                            log.error(f"Error cleaning up orphaned directory {session_dir}: {e}")
        except Exception as e:
            log.error(f"Error during final downloads directory cleanup: {e}")

    def start(self):
        if self._task is None:
            self._task = create_task(self.auto_delete_file_task())

    def get_file_url(self, session_id: str) -> Optional[str]:
        """Get the file URL, either from R2 or local storage"""
        file_path = self.storage.get(session_id)
        if not file_path:
            return None
            
        if self.r2_storage.enabled:
            # When using R2, file_path[0] is just the filename
            filename = file_path[0].name if isinstance(file_path[0], pathlib.Path) else file_path[0]
            object_name = f"{session_id}/{filename}"
            return self.r2_storage.get_presigned_url(object_name, FILE_EXPIRE_TIME)
        return None

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
        super().__init__(lifespan=self.lifespan,
                        docs_url="/docs" if IS_DEVELOPMENT else None,
                        redoc_url="/redoc" if IS_DEVELOPMENT else None,
                        openapi_url="/openapi.json" if IS_DEVELOPMENT else None)

        self.add_api_route("/fetch_data", self.get_all_formats, response_model=DataResponse, methods=["POST"],
                            dependencies=[Depends(verify_token)])

        self.add_api_route("/download", self.download_video, methods=["POST"]
                            , response_model=DownloadResponse, dependencies=[Depends(verify_token)])

        self.add_api_route("/files/{session_id}", self.get_downloaded_file, methods=["GET"],
                            response_class=FileResponse)

        self.add_api_route("/geo_check", self.check_geo_block, methods=["POST"], response_model=GeoblockData,
                            dependencies=[Depends(verify_token)])

        self.add_api_route("/", self.root, methods=["GET", "HEAD"])

        if ENABLE_TROLLING_ROUTE:
            self.add_api_route("/.env", self.fake_environment, methods=["GET"])

        self.add_exception_handler(404, self.error_handler)
        self.add_exception_handler(405, self.error_handler)

        self.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                        allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
        self.add_middleware(RateLimitMiddleware)

        self.file_session = FileSession()
        self.uptime = datetime.now(timezone.utc)

        if TURNSITE_VERIFICATION:
            self.turnstile = Turnstile(TURNSITE_SECRET_KEY)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Handles application startup and shutdown.
        Starts the auto-delete task and ensures proper cleanup on shutdown.
        """
        try:
            self.file_session.start()
            yield None
        finally:
            await self.file_session.clear_sessions()

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())
    
    # ATTACKER TROLLING ROUTE
    async def fake_environment(self):
        messages = [
            "Yo mon frère, y'a rien ici. Va coder au lieu de fouiller. 🗿🇫🇷",
            "Eh oh, t'as cru trouver quoi ici ? Retourne bosser ! 🥖",
            "Bien essayé mon gars, mais y'a que des baguettes ici. 🥖🇫🇷",
            "Mdr, t'es vraiment en train de chercher des .env ? Trop fort ! 😂",
            "Nope ! Pas de fichiers secrets ici, juste du saucisson. 🍖",
            "Oh là là, encore un petit malin qui fouine ! Allez, retourne coder. 🐌",
            "C'est pas bien de fouiller comme ça ! Tiens, prends un croissant 🥐",
            "404 Baguette Not Found. Réessaie plus tard ! 🥖❌"
        ]
        return {
            "message": random.choice(messages)
        }
    
    async def error_handler(self, request: Request, exc: Exception):
        messages = [
            "Yo mon frère, y'a rien ici. Va coder au lieu de fouiller. 🗿🇫🇷",
            "Eh oh, t'as cru trouver quoi ici ? Retourne bosser ! 🥖",
            "Bien essayé mon gars, mais y'a que des baguettes ici. 🥖🇫🇷",
            "Mdr, t'es vraiment en train de chercher des .env ? Trop fort ! 😂",
            "Nope ! Pas de fichiers secrets ici, juste du saucisson. 🍖",
            "Oh là là, encore un petit malin qui fouine ! Allez, retourne coder. 🐌",
            "C'est pas bien de fouiller comme ça ! Tiens, prends un croissant 🥐",
            "404 Baguette Not Found. Réessaie plus tard ! 🥖❌"
        ]
        route = request.url.path
        ip = request.client.host

        log.warning(f"[{ip}] - [{route}] - [{exc}]")


        return Response(
            content=random.choice(messages),
            status_code=200
        )

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
        fetch_subtitle = request.fetch_subtitle or False

        if not url.strip():
            raise HTTPException(status_code=400, detail="URL is required")

        try:
            # Check format cache first
            cached_format = self.file_session.format_cache.get_cached_format(url)
            if cached_format:
                formats, file_name, subtitle_info = cached_format
                return DataResponse(
                    name=file_name,
                    formats=formats,
                    subtitle_info=subtitle_info
                )

            # If not in cache, fetch from yt-dlp
            formats, file_name, subtitle_info = await s2a(fetch_data)(url, max_audio=3, fetch_subtitle=fetch_subtitle)
            if not formats:
                log.error(f"Fail to load formats for {url}")
                raise HTTPException(status_code=404, detail="No formats found")
            
            # Cache the format information
            self.file_session.format_cache.put_cached_format(url, formats, file_name, subtitle_info)
            
            return DataResponse(
                name=file_name,
                formats=formats,
                subtitle_info=subtitle_info
            )
        except Exception as e:
            log.error("An error occurred while fetching data:", str(e))
            raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    async def download_video(self, request_data: DownloadRequest, request: Request):
        url = request_data.url
        format_option = request_data.format
        subtitle = request_data.subtitle or None
        if TURNSITE_VERIFICATION:
            if not request_data.cf_turnstile_token:
                raise HTTPException(status_code=400, detail="Turnstile token is required")
            is_valid = await self.turnstile.verify_token(request_data.cf_turnstile_token, request.client.host)
            if not is_valid:
                raise HTTPException(status_code=403, detail="Invalid turnstile token")

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Check cache first
        cached_file = self.file_session.url_cache.get_cached_file(url, format_option)
        if cached_file:
            if self.file_session.r2_storage.enabled:
                presigned_url = self.file_session.r2_storage.get_presigned_url(
                    cached_file["object_name"],
                    FILE_EXPIRE_TIME
                )
                if presigned_url:
                    return DownloadResponse(
                        message="Download completed (cached)",
                        filename=cached_file["filename"],
                        download_link=f"/files/{cached_file['session_id']}",
                        expires_at=datetime.now(timezone.utc).timestamp() + FILE_EXPIRE_TIME,
                        expires_in=FILE_EXPIRE_TIME,
                    )

        session_id = self.generate_uuid()
        output = pathlib.Path(os.path.join(DOWNLOAD_FOLDER / session_id))
        output.mkdir(parents=True, exist_ok=True)

        try:
            result = await s2a(run_yt_dlp_download)(url, format_option, subtitle, output)

            if result["success"]:
                filename = resolve_file_name_from_folder(str(output))
                full_file_path = output / filename

                # If R2 storage is enabled, try to upload the file
                if self.file_session.r2_storage.enabled:
                    object_name = f"{session_id}/{filename}"
                    if await s2a(self.file_session.r2_storage.upload_file)(str(full_file_path), object_name):
                        # File uploaded to R2 successfully, delete local copy
                        rmtree(output)
                        # Cache the file information
                        self.file_session.url_cache.cache_file(
                            url,
                            format_option,
                            {
                                "session_id": session_id,
                                "object_name": object_name,
                                "filename": filename
                            },
                            FILE_EXPIRE_TIME
                        )
                        # Store only filename in session
                        self.file_session.add_session(session_id, pathlib.Path(filename))
                    else:
                        # R2 upload failed, keep local file as fallback
                        self.file_session.add_session(session_id, output)
                else:
                    # R2 not enabled, store locally
                    self.file_session.add_session(session_id, output)

                return DownloadResponse(
                    message="Download completed",
                    filename=filename,
                    download_link=f"/files/{session_id}",
                    expires_at=datetime.now(timezone.utc).timestamp() + FILE_EXPIRE_TIME,
                    expires_in=FILE_EXPIRE_TIME,
                )
            else:
                if output.exists():
                    rmtree(output)
                return Response(
                    content="Download failed",
                    status_code=500
                )
        except yt_dlp.utils.DownloadError:
            if output.exists():
                rmtree(output)
            return Response(
                content="Download failed",
                status_code=500,
            )
        except FileNotFoundError:
            if output.exists():
                rmtree(output)
            return Response(
                content="Download Failed",
                status_code=500
            )

    async def get_downloaded_file(self, session_id: str):
        if not is_valid_uuid4(session_id):
            raise HTTPException(400, detail="Invalid session ID")

        # Check if we have an R2 URL
        if self.file_session.r2_storage.enabled:
            r2_url = self.file_session.get_file_url(session_id)
            if r2_url:
                return RedirectResponse(url=r2_url)

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

        return HTMLResponse(content=open("template/gomen.html").read())
    
    async def root(self):
        beautiful_format = ""
        for route in self.routes:
            beautiful_format += f"[ [{route.name}] - [{route.methods}] - [{route.path}] ]"
        return {"message": f"Server is running - {beautiful_format} - Last restart: {self.uptime.ctime()}"}

if __name__ == "__main__":
    import uvicorn
    log.info(f"YT-DLP VERSION: {yt_dlp.version.__version__}")
    uvicorn.run(BaseApplication, host="0.0.0.0", port=8000, log_config=LOGGING_CONFIG, forwarded_allow_ips=UVICORN_FORWARDED_ORIGINS)