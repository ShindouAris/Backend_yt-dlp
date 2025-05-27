from manager.LRU_cache.LRU_NODE import LRUCache
from manager.ytdlp_tool.ytdl_tools import FormatInfo
from manager.models.subtitle_model import SubtitleInfo
from typing import Optional, Tuple, List


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
            cached_data = self.get(url)
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
            self.put(url, (format_data, filename, subtitle_info))
        except Exception as e:
            print(f"Error putting cached format for {url}: {e}")

    def delete_cached_format(self, url: str) -> None:
        """
        Delete cached format information for a URL.
        
        Args:
            url: The URL to delete format information for
        """
        try:
            self.delete(url)
        except Exception as e:
            print(f"Error deleting cached format for {url}: {e}")


