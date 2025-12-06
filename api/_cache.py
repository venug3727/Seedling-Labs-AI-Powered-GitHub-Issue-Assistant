"""
Shared Cache Utility for Vercel Serverless Functions.

Provides in-memory caching with TTL for cost & latency optimization.
Note: Vercel keeps functions warm for a period, so cache persists across requests.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any

# Global cache storage (persists across requests in warm instances)
_cache: Dict[str, Tuple[Any, datetime]] = {}
_cache_ttl = timedelta(minutes=60)


def generate_cache_key(*args) -> str:
    """Generate a unique cache key from arguments."""
    raw_key = ":".join(str(arg) for arg in args)
    return hashlib.md5(raw_key.encode()).hexdigest()


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache if not expired."""
    if key in _cache:
        value, cached_at = _cache[key]
        if datetime.now() - cached_at < _cache_ttl:
            return value
        else:
            # Expired, remove from cache
            del _cache[key]
    return None


def cache_set(key: str, value: Any) -> None:
    """Store value in cache with timestamp."""
    _cache[key] = (value, datetime.now())


def get_cached_or_fetch(cache_key: str, fetch_func, *args, **kwargs) -> Tuple[Any, bool]:
    """
    Get from cache or fetch using provided function.
    
    Returns:
        Tuple[result, was_cached]
    """
    cached = cache_get(cache_key)
    if cached is not None:
        return cached, True
    
    result = fetch_func(*args, **kwargs)
    cache_set(cache_key, result)
    return result, False
