from typing import Optional
import asyncio
import yt_dlp
from pydantic import BaseModel
import pathlib
from logging import getLogger
from manager.regex_manager.regex_manager import get_provider_from_url, is_youtube_playlist, resolve_url, normalize_facebook_url
from manager.models.subtitle_model import SubtitleInfo
import aiohttp
import urllib.parse
from os import environ
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
        case "x":
            return "./x_cookie.txt"
        case "facebook_story":
            return None # Story isn't fetch from yt-dlp, use api instead
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

def build_story_format(story_data: dict) -> list[FormatInfo]:
    result: list[FormatInfo] = []
    
    for story in story_data["data"]["stories"]:
        video_formats = sorted(
            story["muted"],
            key=lambda x: x.get("height", 0),
            reverse=True
        )
        
        audio_url = story.get("audio", "")
        
        for video in video_formats:
            height = video.get("height", 0)
            width = video.get("width", 0)
            bandwidth = video.get("bandwidth", 0)
            
            bitrate_mbps = round(bandwidth / 1024 / 1024, 2)
            
            label = f"{height}p ({width}x{height}) {bitrate_mbps}Mbps + Audio"
            
            if audio_url:
                result.append(
                    FormatInfo(
                        type="video+audio",
                        format=f"fb-story-{height}p-merged",
                        label=label,
                        video_format=video["url"],
                        audio_format=audio_url,
                        note=f"Combined video and audio, Resolution: {width}x{height}"
                    )
                )
        
        # Add video-only formats
        for video in video_formats:
            height = video.get("height", 0)
            width = video.get("width", 0)
            bandwidth = video.get("bandwidth", 0)
            bitrate_mbps = round(bandwidth / 1024 / 1024, 2)
            
            label = f"{height}p ({width}x{height}) {bitrate_mbps}Mbps [Video Only]"
            
            result.append(
                FormatInfo(
                    type="video-only",
                    format=f"fb-story-{height}p",
                    label=label,
                    video_format=video["url"],
                    audio_format="",
                    note=f"Video only, Resolution: {width}x{height}"
                )
            )
        if audio_url:
            result.append(
                FormatInfo(
                    type="audio-only",
                    format="fb-story-audio",
                    label="Audio Track",
                    video_format="none",
                    audio_format=audio_url,
                    note="Audio only track"
                )
            )
    
    return result

if not environ.get("STORIE_API_URL"):
    fb_story_api_supported = False
else:
    fb_story_api_supported = True

async def fetch_story_data(fb_url: str, method: str = "html") -> dict:
    try:
        normalized_url = normalize_facebook_url(fb_url)

        # Double encode the normalized URL
        encoded_url = urllib.parse.quote(normalized_url, safe="")
        encoded_url = urllib.parse.quote(encoded_url, safe="")

        api_url = environ.get("STORIE_API_URL").format(encoded_url=encoded_url, method=method)

        if not api_url:
            raise ValueError("STORIE_API_URL is not set")

        headers = {
            "User-Agent": "Mozilla/5.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    print("✅ Success")
                    return await response.json()
                else:
                    print(f"❌ HTTP {response.status}")
                    print(await response.text())
                    return {}
    except Exception as e:
        print("❌ Error:", str(e))
        return {}

def fetch_data(url: str, max_audio: int = 3, fetch_subtitle: bool = True) -> tuple[
    list[FormatInfo], str | None, Optional[SubtitleInfo]
]:
    """
    Fetch format data and subtitle information from a URL
    
    Args:
        url: The URL to fetch from
        max_audio: Maximum number of audio formats to return
        fetch_subtitle: Whether to fetch subtitle information
        
    Returns:
        Tuple of (format_list, filename, subtitle_info)
    """
    opt = {
        "quiet": True,
        "no_warnings": True,
        "logger": log,
        "ignoreerrors": True,
        "writesubtitles": fetch_subtitle,
        "allsubtitles": fetch_subtitle,
    }

    platform = get_provider_from_url(url)

    if platform == "facebook_story" and fb_story_api_supported:
        url = normalize_facebook_url(url)
        story_data = asyncio.run(fetch_story_data(url))
        return build_story_format(story_data), url, None

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
            return [], None, None

        filename = ydl.prepare_filename(info)
        raw_formats = info.get("formats", [])
        subtitle_info = None
        
        if fetch_subtitle:
            subtitles = info.get("subtitles", {})
            
            if subtitles:
                all_subtitles = {**subtitles}
                subtitle_info = SubtitleInfo.from_yt_dlp_data(all_subtitles)
                
        
        if not raw_formats:
            print("No formats found in extracted info.")
            return [], filename, subtitle_info
        
        
        log.debug(f"Starting to process formats for {platform} platform")
        
        if platform == "tiktok":
            video_formats = [
                f for f in raw_formats
                if f.get("vcodec") != "none" and f.get("height") is not None
            ]
            video_formats = sorted(video_formats, key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)

            result: list[FormatInfo] = []
            seen_resolutions = set()

            for f in video_formats:
                video_height = f.get("height", 0)
                video_ext = f.get("ext")
                video_codec = f.get("vcodec", "unknown")
                resolution_key = f"{video_height}p_{video_codec}"

                if resolution_key in seen_resolutions:
                    continue
                
                seen_resolutions.add(resolution_key)

                # Create a more descriptive label
                label = f"{video_height}p ({video_codec})"

                result.append(
                    FormatInfo(
                        type="video+audio",
                        format=f['format_id'],
                        label=label,
                        video_format=f['format_id'],
                        audio_format="default - muxed", 
                        note=f.get("format_note") or f"Resolution: {f.get('width')}x{f.get('height')}"
                    )
                )

            if len(result) < 1:
                result = default_formatData

            return result, filename, subtitle_info if fetch_subtitle else None

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

                label = f"{video_height}p ({video_ext}) [Audio: {audio_bitrate_kbps}Kbps]".strip()

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

        return result, filename, subtitle_info


def run_yt_dlp_download(url: str, format_option: str, subtitle: str, output: pathlib.Path):
    """
    Runs yt-dlp in a subprocess.
    This function is designed to be run in a background task or awaited.
    
    Args:
        url: URL to download from
        format_option: Format ID for video/audio
        subtitle: Subtitle language code (e.g., 'en', 'ja', or None)
        output: Output directory path
        
    Returns:
        Dictionary with download results
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

    if subtitle is not None:
        ydl_opts.update({
            'writesubtitles': True,
            'writeautomaticsub': True,  
            'subtitleslangs': [subtitle],
            'subtitlesformat': 'best', 
            'embedsubtitles': True,     
            'postprocessors': [{
                'key': 'FFmpegEmbedSubtitle',
                'already_have_subtitle': False 
            }]
        })

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

    if platform == "facebook_story" and fb_story_api_supported:
        ... # Comming soon™

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

