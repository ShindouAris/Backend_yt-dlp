from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class SubtitleFormat(BaseModel):
    """Individual subtitle format details"""
    ext: str = Field(description="File extension (e.g., vtt, srt, json3)")
    url: str = Field(description="URL to download the subtitle")
    name: Optional[str] = Field(default=None, description="Display name of the subtitle track")


class SubtitleTrack(BaseModel):
    """Subtitle track for a specific language"""
    formats: List[SubtitleFormat] = Field(description="List of available formats for this language")
    language_code: str = Field(description="ISO language code (e.g., en, ja, ko)")
    language_name: str = Field(description="Display name of the language")

    @property
    def best_format(self) -> Optional[SubtitleFormat]:
        """Get the best format in preferred order: vtt > srt > ttml > json3 > srv3"""
        format_priority = ['vtt', 'srt', 'ttml', 'json3', 'srv3']
        for fmt in format_priority:
            for format in self.formats:
                if format.ext == fmt:
                    return format
        return self.formats[0] if self.formats else None


class SubtitleInfo(BaseModel):
    """Complete subtitle information for a video"""
    tracks: Dict[str, SubtitleTrack] = Field(description="Dictionary of subtitle tracks by language code")
    automatic_captions: bool = Field(default=False, description="Whether these are auto-generated captions")
    manual_captions: bool = Field(default=False, description="Whether these are manually created captions")

    @property
    def available_languages(self) -> List[str]:
        """Get list of available language codes"""
        return list(self.tracks.keys())

    def get_best_format(self, language_code: str) -> Optional[SubtitleFormat]:
        """Get the best available format for a specific language"""
        if language_code in self.tracks:
            return self.tracks[language_code].best_format
        return None

    @classmethod
    def from_yt_dlp_data(cls, data: dict) -> "SubtitleInfo":
        """Create SubtitleInfo from yt-dlp subtitle data"""
        tracks = {}
        automatic = False
        manual = False

        for lang_code, formats in data.items():
            if lang_code == "live_chat":  # Skip live chat
                continue

            
            for fmt in formats:
                if fmt["ext"] == "json3":
                    continue
                subtitle_formats = [
                    SubtitleFormat(
                        ext=fmt["ext"],
                    url=fmt["url"],
                    name=fmt.get("name")
                )
            ]

            tracks[lang_code] = SubtitleTrack(
                formats=subtitle_formats,
                language_code=lang_code,
                language_name=formats[0].get("name", lang_code)
            )

            if any("asr" in fmt["url"] for fmt in formats):
                automatic = True
            else:
                manual = True

        #  `all` is a special language code that represents all available subtitles
        tracks["all"] = SubtitleTrack(
            formats=subtitle_formats,
            language_code="all",
            language_name="All"
        )

        return cls(
            tracks=tracks,
            automatic_captions=automatic,
            manual_captions=manual
        ) 
    
