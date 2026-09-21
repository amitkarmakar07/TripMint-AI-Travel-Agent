import os
import json
import logging
from typing import Any, Optional
import certifi
import redis
from config import config

logger = logging.getLogger("tripmint.cache")

# Local in-memory fallback dict
_memory_cache: dict[str, Any] = {}

redis_client: Optional[redis.Redis] = None

redis_url = getattr(config, "REDIS_URL", None) or os.getenv("REDIS_URL")

if redis_url:
    try:
        # Support TLS for Upstash / cloud endpoints (rediss://)
        ssl_kwargs = {}
        if redis_url.startswith("rediss://"):
            ssl_kwargs = {
                "ssl_ca_certs": certifi.where(),
                "ssl_cert_reqs": None
            }

        redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            **ssl_kwargs
        )
        # Test ping
        redis_client.ping()
        print("[Cache] Connected to Cloud Redis Cache successfully!")
    except Exception as err:
        print(f"[Cache Warning] Redis connection fallback to in-memory cache: {err}")
        redis_client = None
else:
    print("[Cache Info] REDIS_URL not configured. Operating in local memory cache mode.")


def get_cached(key: str) -> Optional[Any]:
    """Retrieve data from Redis or fallback in-memory cache."""
    if redis_client:
        try:
            val = redis_client.get(key)
            if val is not None:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Redis get error for {key}: {e}")

    # Fallback to in-memory cache
    return _memory_cache.get(key)


def set_cached(key: str, data: Any, ttl_seconds: int = 43200) -> None:
    """Save data to Redis (with TTL) and fallback in-memory cache."""
    # Always keep in memory fallback
    _memory_cache[key] = data

    if redis_client:
        try:
            serialized = json.dumps(data, default=str)
            redis_client.setex(key, ttl_seconds, serialized)
        except Exception as e:
            logger.warning(f"Redis set error for {key}: {e}")


def check_rate_limit(client_ip: str, max_requests: int = 10, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Sliding/fixed window rate limiter per client IP using Redis (with fail-open fallback).
    Returns (is_allowed, remaining_requests).
    """
    key = f"ratelimit:{client_ip}"
    if redis_client:
        try:
            current = redis_client.incr(key)
            if current == 1:
                redis_client.expire(key, window_seconds)
            if current > max_requests:
                return False, 0
            return True, max(0, max_requests - current)
        except Exception as e:
            logger.warning(f"Rate limiter Redis error: {e}")
            return True, max_requests
            
    return True, max_requests
