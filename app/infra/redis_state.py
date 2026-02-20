from __future__ import annotations

import os
from functools import lru_cache

from redis import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    return Redis.from_url(REDIS_URL, decode_responses=True)


def check_redis_ready() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
