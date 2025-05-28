from manager.LRU_cache.LRU_NODE import LRUCache
from manager.ytdlp_tool.ytdl_tools import FormatInfo
from manager.models.subtitle_model import SubtitleInfo
from typing import Optional, Tuple, List
import re
from urllib.parse import urlparse, parse_qs


def normalize_youtube_url(url: str) -> str:
    """
    Normalize YouTube URLs to a consistent format for caching.
    Handles various YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    etc.
    
    Returns:
        Normalized URL in format "youtube:VIDEO_ID"
    """
    # YouTube video ID patterns
    youtube_patterns = [
        r'(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu\.be/)([^"&?/\s]{11})',
        r'youtube\.com/shorts/([^"&?/\s]{11})'
    ]
    
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f"youtube:{video_id}"
    
    # If no pattern matches, return original URL
    return url


class FormatCache(LRUCache):
    def __init__(self, capacity: int, expire_seconds: int):
        super().__init__(capacity, expire_seconds)

    def get_cached_format(self, url: str) -> Optional[Tuple[List[FormatInfo], str, Optional[SubtitleInfo]]]:
        """
        Get cached format information for a URL.
        
        Args:
            url: The URL to get format information for
            
        Returns:
            Tuple of (format_list, filename, subtitle_info) if found in cache, None otherwise
        """
        try:
            normalized_url = normalize_youtube_url(url)
            cached_data = self.get(normalized_url)
            if cached_data:
                return cached_data
        except Exception as e:
            print(f"Error getting cached format for {url}: {e}")
            return None

    def put_cached_format(self, url: str, format_data: List[FormatInfo], filename: str, subtitle_info: Optional[SubtitleInfo]) -> None:
        """
        Cache format information for a URL.
        
        Args:
            url: The URL to cache format information for
            format_data: List of format information
            filename: The filename associated with the URL
            subtitle_info: Optional subtitle information
        """
        try:
            normalized_url = normalize_youtube_url(url)
            self.put(normalized_url, (format_data, filename, subtitle_info))
        except Exception as e:
            print(f"Error putting cached format for {url}: {e}")

    def delete_cached_format(self, url: str) -> None:
        """
        Delete cached format information for a URL.
        
        Args:
            url: The URL to delete format information for
        """
        try:
            normalized_url = normalize_youtube_url(url)
            self.delete(normalized_url)
        except Exception as e:
            print(f"Error deleting cached format for {url}: {e}")


