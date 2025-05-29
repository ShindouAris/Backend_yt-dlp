from pydantic import BaseModel
from manager.models.subtitle_model import SubtitleInfo
from manager.configuation.config import TURNSITE_VERIFICATION

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
    if TURNSITE_VERIFICATION:
        cf_turnstile_token: str | None = None

class FormatRequest(BaseModel):
    url: str
    fetch_subtitle: bool = False

class FormatInfo(BaseModel):
    type: str
    format: str
    label: str
    video_format: str | None = None
    audio_format: str | None = None
    note: str | None = None
    
class DataResponse(BaseModel):
    name: str
    formats: list[FormatInfo]
    subtitle_info: SubtitleInfo | None = None
