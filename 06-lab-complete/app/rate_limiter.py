"""Redis-backed sliding-window rate limiter."""
import time

import redis
from fastapi import HTTPException

from app.config import settings


class RedisRateLimiter:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.limit = settings.rate_limit_per_minute
        self.window_seconds = 60

    def check(self, user_id: str) -> dict:
        now = time.time()
        key = f"rate:{user_id}"
        window_start = now - self.window_seconds

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        _, current_count = pipe.execute()

        if current_count >= self.limit:
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = self.window_seconds
            if oldest:
                retry_after = max(1, int(oldest[0][1] + self.window_seconds - now))
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.limit,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        member = f"{now}:{user_id}"
        pipe = self.redis.pipeline()
        pipe.zadd(key, {member: now})
        pipe.expire(key, self.window_seconds * 2)
        pipe.execute()
        return {"limit": self.limit, "remaining": self.limit - current_count - 1}


rate_limiter = RedisRateLimiter()
