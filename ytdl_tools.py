from typing import Any

import yt_dlp
from pydantic import BaseModel
import pathlib
from logging import getLogger
from regex_manager import get_provider_from_url, is_youtube_playlist, resolve_url

log = getLogger(__name__)

class FormatInfo(BaseModel):
    type: str
    format: str
    label: str
    video_format: str | None = None
    audio_format: str | None = None
    note: str | None = None

def get_cookie_file(platform: str) -> str:
    """
    Returns the path to the cookie file for a given platform.
    """
    match platform.lower():
        case "youtube":
            return "./cookie.txt"
        case "tiktok":
            return "./tiktok_cookie.txt"
        case "instagram":
            return "./instagram_cookie.txt"
        case "facebook":
            return "./facebook_cookie.txt"
        case _:
            return f"./{str(platform).lower().replace(' ', '_')}_cookie.txt"

default_formatData = [
    FormatInfo(
        type="video+audio",
        format=f"best",
        label="Best_setting",
        video_format="best",
        audio_format="best",
        note="Default data, no format found"
    ),
    FormatInfo(
        type="audio-only",
        format=f"bestaudio",
        label="Best audio setting",
        video_format=None,
        audio_format="best",
        note="Default data, no format found"
    ),
    FormatInfo(
        type="video-only",
        format=f"bestvideo",
        label="Best video setting",
        video_format="best",
        audio_format=None,
    )
]

def fetch_format_data(url: str, max_audio: int = 3) -> tuple[
    list[FormatInfo], Any
]:

    opt = {
        "quiet": True,
        "no_warnings": True,
        "logger": log,
        "ignoreerrors": True,
    }

    platform = get_provider_from_url(url)
    if platform:
        cookiefile = get_cookie_file(platform)
        opt["cookiefile"] = cookiefile
    else:
        opt["cookiefile"] = "./yt_dlp_cookie.txt"

    if platform == "youtube" and is_youtube_playlist(url):
        url = resolve_url(url)

    with yt_dlp.YoutubeDL(opt) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            print(f"Error extracting info: {e}")
            return [], None

        filename = ydl.prepare_filename(info)
        raw_formats = info.get("formats", [])
        if not raw_formats:
            print("No formats found in extracted info.")
            return [], filename

        video_formats = [
            f for f in raw_formats
            if f.get("vcodec") != "none" and f.get("acodec") == "none" and f.get("height") is not None
        ]

        audio_formats = [
            f for f in raw_formats
            if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("abr")
        ]
        audio_formats = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[:max_audio]

        result: list[FormatInfo] = []

        for v in sorted(video_formats, key=lambda x: x.get("height") or 0, reverse=True):
            log.debug(f"Video format: {v}")
            log.debug(f"Audio formats: {audio_formats}")
            video_height = v.get("height", 0)
            video_ext = v.get("ext")

            if video_ext == "webm" and video_height <= 1080:
                continue

            if v.get("format_note") is None and platform == "youtube":
                continue # skip shit

            for a in audio_formats:
                audio_bitrate_kbps = round(a.get('abr', 0), 1)

                if audio_bitrate_kbps <= 66.7 and platform == "youtube":
                    continue

                label = f"{video_height}p ({video_ext}) [Audio: {audio_bitrate_kbps}Kbps] {'[PREMIUM]' if str(v.get('format_note')).lower() == 'premium' else ''}".strip()

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
                    video_format=None,
                    audio_format=a['format_id'],
                    note=a.get("format_note")
                )
            )

        for v in video_formats:
            label = f"Video only: {v.get('height')}p ({v.get('ext')})"
            result.append(
                FormatInfo(
                    type="video-only",
                    format=v['format_id'],
                    label=label,
                    video_format=v['format_id'],
                    audio_format=None,
                    note=v.get("format_note")
                )
            )

        if len(result) < 1:
            result = default_formatData

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
        'logger': log,
    }
    platform = get_provider_from_url(url)
    if platform:
        cookie_file = get_cookie_file(platform)
        ydl_opts["cookiefile"] = cookie_file
    else:
        log.warning(f"Platform not recognized for URL: {url}. Using default cookie file.")
        ydl_opts["cookiefile"] = "./yt_dlp_cookie.txt"

    # Refuse to download playlists, resolve to the first video in the playlist
    if platform == "youtube" and is_youtube_playlist(url):
        url = resolve_url(url)

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

