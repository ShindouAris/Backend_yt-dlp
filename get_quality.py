from typing import Tuple, List, Any

import yt_dlp
from pydantic import BaseModel
import pathlib

class FormatInfo(BaseModel):
    type: str
    format: str
    label: str
    video_format: str | None = None
    audio_format: str | None = None
    note: str | None = None

def fetch_format_data(url, max_audio=3, cookiefile: pathlib.Path = pathlib.Path("./cookie.txt") ) -> tuple[
    list[FormatInfo], Any]:

    opt = {
        "quiet": True
    }
    if cookiefile is not None and cookiefile.exists() and cookiefile.is_file():
        opt["cookies"] = str(cookiefile)
    else:
        opt["cookies"] = "./cookie.txt"

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

#
# if __name__ == '__main__':
#
#     url = "https://youtu.be/jMSXPPSmsVo"
#     import uuid
#     def generate_uuid():
#         return str(uuid.uuid4())
#     session_id = generate_uuid()
#     results = fetch_format_data(url)
#     for item in results:
#         print(item)
#     import pathlib
#     p = pathlib.Path(f"./logs/{session_id}")
#     p.mkdir(parents=True, exist_ok=True)
#     with open(p / "formats.json", "w") as f:
#         import json
#         json.dump(results, f, indent=4)
