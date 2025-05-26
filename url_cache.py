import redis
import os
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

class URLCache:
    def __init__(self):
        self.enabled = os.environ.get("USE_REDIS_CACHE", "false").lower() == "true"
        if not self.enabled:
            # Fallback to in-memory cache if Redis is not enabled
            self.memory_cache: Dict[str, Dict[str, Any]] = {}
            return

        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_password = os.environ.get("REDIS_PASSWORD")

        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )

    def _get_cache_key(self, url: str, format_option: str) -> str:
        """Generate a cache key from URL and format option"""
        return f"ytdl:{url}:{format_option}"

    def get_cached_file(self, url: str, format_option: str) -> Optional[Dict[str, Any]]:
        """Get cached file information if it exists"""
        cache_key = self._get_cache_key(url, format_option)

        if not self.enabled:
            # Use in-memory cache
            cached_data = self.memory_cache.get(cache_key)
            if cached_data:
                expiry_time = datetime.fromisoformat(cached_data['expiry_time'])
                if expiry_time > datetime.utcnow():
                    return cached_data
                else:
                    del self.memory_cache[cache_key]
            return None

        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            log.error(f"Error retrieving from cache: {e}")
            return None

    def cache_file(self, url: str, format_option: str, file_info: Dict[str, Any], 
                  expire_time: int = 1800) -> bool:
        """Cache file information with expiration"""
        cache_key = self._get_cache_key(url, format_option)
        expiry_time = datetime.utcnow() + timedelta(seconds=expire_time)
        file_info['expiry_time'] = expiry_time.isoformat()

        if not self.enabled:
            # Use in-memory cache
            self.memory_cache[cache_key] = file_info
            return True

        try:
            self.redis.setex(
                cache_key,
                expire_time,
                json.dumps(file_info)
            )
            # Store a reverse lookup for session cleanup
            session_key = f"session:{file_info['session_id']}"
            self.redis.sadd(session_key, cache_key)
            self.redis.expire(session_key, expire_time)
            return True
        except Exception as e:
            log.error(f"Error caching file info: {e}")
            return False

    def remove_cache(self, url: str, format_option: str) -> bool:
        """Remove cached file information"""
        cache_key = self._get_cache_key(url, format_option)

        if not self.enabled:
            # Use in-memory cache
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
            return True

        try:
            self.redis.delete(cache_key)
            return True
        except Exception as e:
            log.error(f"Error removing cache: {e}")
            return False

    def remove_all_by_session(self, session_id: str) -> bool:
        """Remove all cache entries associated with a session ID"""
        if not self.enabled:
            # For in-memory cache, iterate and remove matching entries
            keys_to_remove = []
            for key, value in self.memory_cache.items():
                if value.get('session_id') == session_id:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.memory_cache[key]
            return True

        try:
            # Get all cache keys associated with this session
            session_key = f"session:{session_id}"
            cache_keys = self.redis.smembers(session_key)
            
            if cache_keys:
                # Delete all cache entries and the session set
                self.redis.delete(*cache_keys, session_key)
            return True
        except Exception as e:
            log.error(f"Error removing cache for session {session_id}: {e}")
            return False 