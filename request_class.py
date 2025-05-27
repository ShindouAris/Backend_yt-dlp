from pydantic import BaseModel

from manager.ytdlp_tool.ytdl_tools import FormatInfo
from manager.models.subtitle_model import SubtitleInfo

class DownloadResponse(BaseModel):
    message: str
    filename: str | None = None
    download_link: str | None = None
    details: str | None = None
    yt_dlp_output: str | None = None
    expires_at: float | None = None
    expires_in: int | None = None

class DownloadRequest(BaseModel):
    url: str
    format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
    subtitle: str | None = None

class FormatRequest(BaseModel):
    url: str
    fetch_subtitle: bool = False

class DataResponse(BaseModel):
    name: str
    formats: list[FormatInfo]
    subtitle_info: SubtitleInfo | None = None