"""Redis-backed monthly budget guard."""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def seconds_until_next_month() -> int:
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return max(1, int((next_month - now).total_seconds()))


class CostGuard:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.monthly_budget_usd = settings.monthly_budget_usd

    def _key(self, user_id: str) -> str:
        return f"budget:{user_id}:{current_month()}"

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS
            + output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS
        )

    def check_budget(
        self, user_id: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        key = self._key(user_id)
        current = float(self.redis.hget(key, "cost_usd") or 0)
        estimated_cost = self._cost(input_tokens, output_tokens)
        if current + estimated_cost > self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(current, 6),
                    "estimated_cost_usd": round(estimated_cost, 6),
                    "budget_usd": self.monthly_budget_usd,
                    "resets_at": "first day of next month UTC",
                },
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> dict:
        self.check_budget(user_id, input_tokens, output_tokens)
        key = self._key(user_id)
        cost = self._cost(input_tokens, output_tokens)
        expiry = seconds_until_next_month() + 24 * 3600

        pipe = self.redis.pipeline()
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        pipe.hincrby(key, "request_count", 1)
        pipe.hincrbyfloat(key, "cost_usd", cost)
        pipe.expire(key, expiry)
        pipe.execute()

        total_cost = float(self.redis.hget(key, "cost_usd") or 0)
        return {
            "cost_usd": round(total_cost, 6),
            "budget_usd": self.monthly_budget_usd,
            "remaining_usd": round(max(0, self.monthly_budget_usd - total_cost), 6),
        }


cost_guard = CostGuard()
