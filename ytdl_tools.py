from typing import Any

import yt_dlp
from fastapi import HTTPException
from pydantic import BaseModel
import pathlib
from logging import getLogger

log = getLogger(__name__)

class FormatInfo(BaseModel):
    type: str
    format: str
    label: str
    video_format: str | None = None
    audio_format: str | None = None
    note: str | None = None

cookie_file = "./cookie.txt"

def fetch_format_data(url, max_audio=3, cookiefile = "./cookie.txt" ) -> tuple[
    list[FormatInfo], Any]:

    opt = {
        "quiet": True
    }
    if cookiefile:
        opt["cookiefile"] = cookiefile

    with yt_dlp.YoutubeDL(opt) as ydl:

        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
        formats = info.get("formats", [])

        video_formats = [
            f for f in formats
            if f.get("vcodec") != "none" and f.get("acodec") == "none"
        ]

        audio_formats = [
            f for f in formats
            if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("abr")
        ]

        audio_formats = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[:max_audio]

        result: list[FormatInfo] = []

        for v in sorted(video_formats, key=lambda x: x.get("height") or 0, reverse=True):
            for a in audio_formats:
                label = f"{v.get('height', '?')}p ({v.get('ext')}) [Audio: {round(a.get('abr', 0), 1)}Kbps] {'[PREMIUM]' if str(v.get('format_note')).lower() == 'premium' else ''}"
                if round(a.get('abr', 0), 1) <= 66.7:
                    continue
                if v.get("ext") == "webm":
                    continue
                if v.get("format_note") is None:
                    continue # skip shit
                result.append(
                    FormatInfo(
                        type="video+audio",
                        format=f"{v['format_id']}+{a['format_id']}",
                        label=label,
                        video_format=v['format_id'],
                        audio_format=a['format_id'],
                        note=v.get("format_note")
                    )
                )

        for a in audio_formats:
            label = f"Audio only: {round(a.get('abr', 0), 1)}kbps ({a.get('ext')})"
            result.append(
                FormatInfo(
                    type="audio-only",
                    format=a['format_id'],
                    label=label,
                    audio_format=a['format_id'],
                    note=a.get("format_note")
                )
            )

        return result, filename


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
            log.debug(f"USE COOKIE: {ydl_opts.get('cookiefile', 'NO')}")
            info_dict = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info_dict)
            log.debug(f"Extracted filename: {filename}")
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