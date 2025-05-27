from manager.LRU_cache.LRU_NODE import LRUCache
from manager.ytdlp_tool.ytdl_tools import FormatInfo


class URLCache(LRUCache):
    def __init__(self, capacity: int, expire_seconds: int):
        super().__init__(capacity, expire_seconds)

    def get_cached_format(self, url: str) -> list[FormatInfo] | None:
        try:
            cached_data = self.get(url)
            if cached_data:
                return cached_data
        except Exception as e:
            print(f"Error getting cached format for {url}: {e}")
            return None

    def put_cached_format(self, url: str, format_data: list[FormatInfo]) -> None:
        try:
            self.put(url, format_data)
        except Exception as e:
            print(f"Error putting cached format for {url}: {e}")

    def delete_cached_format(self, url: str) -> None:
        try:
            self.delete(url)
        except Exception as e:
            print(f"Error deleting cached format for {url}: {e}")


