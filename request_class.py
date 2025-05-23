from pydantic import BaseModel

from ytdl_tools import FormatInfo


class DownloadResponse(BaseModel):
    message: str
    filename: str | None = None
    download_link: str | None = None
    details: str | None = None
    yt_dlp_output: str | None = None

class DownloadRequest(BaseModel):
    url: str
    format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

class FormatRequest(BaseModel):
    url: str

class FormatResponse(BaseModel):
    name: str
    formats: list[FormatInfo]