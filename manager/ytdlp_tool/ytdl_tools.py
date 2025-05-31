from typing import Optional
import asyncio
from anyio.from_thread import start_blocking_portal
import yt_dlp
import pathlib
from logging import getLogger
from manager.regex_manager.regex_manager import get_provider_from_url, is_youtube_playlist, resolve_url, normalize_facebook_url
from manager.models.subtitle_model import SubtitleInfo
import aiohttp
import urllib.parse
from os import environ, path
import tqdm
log = getLogger(__name__)
from manager.models.request_class import FormatInfo
from manager.LRU_cache.format_cache import FormatCache  
import aiofiles
from manager.configuation.config import MAX_FILE_SIZE
from fastapi import FastAPI
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


if not environ.get("STORIE_API_URL"):
    fb_story_api_supported = False
else:
    fb_story_api_supported = True

class YTDLP_TOOLS:      
    def __init__(self, app: FastAPI):
        self.app = app
        self.story_cache = FormatCache(capacity=30, expire_seconds=-1)
        self.download_hooks = {}

    def get_cookie_file(self, platform: str) -> str:
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


    def build_story_format(self, story_data: dict) -> list[FormatInfo]:
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

        self.story_cache.put_cached_format(story_data["url"], result, "Story-FB", None)
        
        return result


    async def fetch_story_data(self, fb_url: str, method: str = "html") -> dict:
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
                        response_data = await response.json()
                        response_data["url"] = fb_url
                        return response_data
                    else:
                        log.error(f"❌ HTTP {response.status}")
                        log.error(await response.text())
                        return {}
        except Exception as e:
            log.error(f"❌ Error: {e}")
            return {}

    async def download_story_data(self, fb_url: str, format_id: str, output: pathlib.Path) -> dict:
        cached_data = self.story_cache.get_cached_format(fb_url)
        if not cached_data:
            log.info("Fetching story data from API")
            # Re-fetch it if cache miss
            await self.fetch_story_data(fb_url)
            # try to get it again
            cached_data = self.story_cache.get_cached_format(fb_url)
            if not cached_data:
                # It so over
                log.error(f"Failed to fetch story data for {fb_url}")
                return {
                    "success": False,
                }
        async with aiohttp.ClientSession() as session:
            for formats in cached_data:
                for format in formats:
                    if format.format == format_id:
                        rv = None
                        ra = None
                        if format.video_format:
                            async with session.get(format.video_format) as response:
                                if response.status == 200:
                                    rv = await response.read()

                        if format.audio_format:
                            async with session.get(format.audio_format) as response:
                                if response.status == 200:
                                    ra = await response.read()

                        sw = await self.story_worker(rv, ra, output)

                        if sw:
                            return {
                                "success": True,
                                "file_location": output
                            }

        return {
            "success": False,
        }

    async def story_worker(self, video_bytes: bytes = None, audio_bytes: bytes = None, output: pathlib.Path = None) -> bool:
        # Write file first
        if video_bytes and audio_bytes:
            video_path = output / "video.mp4"
            audio_path = output / "audio.mp3"
            output_path = output / "output.mp4"

            async with aiofiles.open(video_path, "wb") as fv, \
                    aiofiles.open(audio_path, "wb") as fa:
                await asyncio.gather(
                    fv.write(video_bytes),
                    fa.write(audio_bytes)
                )

            # Ensure files exist and have correct sizes
            await asyncio.sleep(0.1)  # Small delay to ensure OS flush

            if not (video_path.exists() and audio_path.exists()):
                log.error(f"Files don't exist: video={video_path.exists()}, audio={audio_path.exists()}")
                return False

            log.info(f"File sizes: video={video_path.stat().st_size}, audio={audio_path.stat().st_size}")

            ffmpeg_task = self.app.ffmpeg_tools.merge_audio(str(video_path), str(audio_path), str(output_path))

            if not ffmpeg_task:
                return False

            audio_path.unlink(missing_ok=True)
            video_path.unlink(missing_ok=True)
            return True


        if video_bytes and not audio_bytes:
            with open(output / "video.mp4", "wb") as fv:
                fv.write(video_bytes)
            
            return True

        if not video_bytes and audio_bytes:
            with open(output / "audio.mp3", "wb") as fa:
                fa.write(audio_bytes)
            
            return True

    def fetch_data(self, url: str, max_audio: int = 3, fetch_subtitle: bool = True) -> tuple[
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
            with start_blocking_portal() as portal:
                story_data = portal.call(self.fetch_story_data, url)
            return self.build_story_format(story_data), url, None

        if platform:
            cookiefile = self.get_cookie_file(platform)
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
                    # Should i add auto-generated subtitles?
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

    

    def hook_download(self, d):
        try:
            filename = d.get('filename', 'unknown')
            status = d.get('status')
            total = d.get('total_bytes', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if status == 'downloading':
                if filename not in self.download_hooks:
                    self.download_hooks[filename] = tqdm.tqdm(
                        total=total,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"Downloading {path.basename(filename)}",
                        bar_format="{desc}: [{bar:30}] {percentage:3.0f}% ({n_fmt}/{total_fmt}) [⏱ {elapsed} < {remaining}]",
                        ascii=" >=",
                        colour="GREEN"
                    )

                    bar = self.download_hooks[filename]
                    bar.n = downloaded
                    bar.refresh()
            elif status == 'finished':
                if filename in self.download_hooks:
                    bar = self.download_hooks[filename]
                    bar.n = total
                    bar.refresh()
                    bar.close()
                    del self.download_hooks[filename]
                    log.info(f"Downloaded {filename} ({total} bytes)")
        except Exception as e:
            log.error(f"Error in hook_download: {e}")

    def run_yt_dlp_download(self, url: str, format_option: str, subtitle: str, output: pathlib.Path):
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
            'ignoreerrors': True,
            'quiet': True,
            'verbose': False,
            'no_warnings': True,
            'simulate': False,
            'extract_flat': False,
            'logger': log,
            'progress_hooks': [self.hook_download],
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
            cookie_file = self.get_cookie_file(platform)
            ydl_opts["cookiefile"] = cookie_file
        else:
            log.warning(f"Platform not recognized for URL: {url}. Using default cookie file.")
            ydl_opts["cookiefile"] = "./yt_dlp_cookie.txt"

        if platform == "youtube" and is_youtube_playlist(url):
            url = resolve_url(url)

        if platform == "facebook_story" and fb_story_api_supported:
            with start_blocking_portal() as portal:
                story_status = portal.call(self.download_story_data, url, format_option, output)
            if not story_status["success"]: # must've the wind
                return {
                    "success": False,
                }
            
            return {
                "success": True,
                "file_location": output,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # Check the file size
            info = ydl.extract_info(url, download=False)

            file_size = info.get("filesize") or info.get("filesize_approx") or 0

            log.info(f"File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            if file_size > MAX_FILE_SIZE * 1024 * 1024:
                return {
                    "success": False,
                    "error": f"Download file size is exceed the limit on this service of {MAX_FILE_SIZE}MB"
                }

            try:
                ydl.download([yt_dlp.utils.sanitize_url(url)])
                return {
                    "success": True,
                    "file_location": output,
                }
            except yt_dlp.utils.DownloadError:
                return {
                    "success": False,
                    "error": "Download failed, please try again later"
                }
            except yt_dlp.utils.ExtractorError:
                return {
                    "success": False,
                    "error": "Extract the video info failed, please contact the developer if this problem persists"
                }
            except yt_dlp.utils.UnavailableVideoError:
                return {
                    "success": False,
                    "error": "The video is not available"
                }
            except Exception as e:
                log.error(f"Error downloading {url}: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

