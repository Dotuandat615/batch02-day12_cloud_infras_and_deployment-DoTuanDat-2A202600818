"""
Production AI Agent - Day 12 final project.

Combines config, API key auth, Redis-backed rate limiting, Redis-backed
conversation history, monthly cost guard, health/readiness, and graceful
shutdown.
"""
from __future__ import annotations

import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import cost_guard
from app.rate_limiter import rate_limiter
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_is_shutting_down = False
_in_flight_requests = 0
_request_count = 0
_error_count = 0

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(user_id: str) -> list[dict]:
    raw_messages = redis_client.lrange(history_key(user_id), 0, -1)
    return [json.loads(message) for message in raw_messages]


def append_history(user_id: str, role: str, content: str) -> None:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = history_key(user_id)
    redis_client.rpush(key, json.dumps(message, ensure_ascii=False))
    redis_client.ltrim(key, -settings.history_max_messages, -1)
    redis_client.expire(key, settings.history_ttl_seconds)


def answer_with_context(question: str, history: list[dict]) -> str:
    normalized = question.lower()
    if "what did i just say" in normalized or "what did i say" in normalized:
        previous_user_messages = [
            item["content"]
            for item in history
            if item.get("role") == "user" and item.get("content") != question
        ]
        if previous_user_messages:
            return f"You just said: {previous_user_messages[-1]}"
    return llm_ask(question)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, _is_shutting_down
    logger.info(json.dumps({"event": "startup", "app": settings.app_name}))
    redis_client.ping()
    _is_shutting_down = False
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    _is_shutting_down = True
    logger.info(json.dumps({"event": "graceful shutdown started"}))
    deadline = time.time() + settings.graceful_shutdown_timeout_seconds
    while _in_flight_requests > 0 and time.time() < deadline:
        time.sleep(0.2)
    logger.info(json.dumps({"event": "graceful shutdown complete"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.exception_handler(redis.RedisError)
async def redis_error_handler(_request: Request, exc: redis.RedisError):
    logger.error(json.dumps({"event": "redis_error", "error": str(exc)}))
    return JSONResponse(
        status_code=503,
        content={"detail": "Redis is temporarily unavailable. Please retry later."},
    )


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count, _in_flight_requests
    start = time.time()
    _request_count += 1
    _in_flight_requests += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round((time.time() - start) * 1000, 1),
        }))
        return response
    except Exception:
        _error_count += 1
        raise
    finally:
        _in_flight_requests -= 1


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    if _is_shutting_down or not _is_ready:
        raise HTTPException(status_code=503, detail="Agent is not ready")

    rate_limiter.check(body.user_id)
    estimated_input_tokens = len(body.question.split()) * 2
    cost_guard.check_budget(body.user_id, estimated_input_tokens, 0)

    append_history(body.user_id, "user", body.question)
    history = load_history(body.user_id)
    answer = answer_with_context(body.question, history)
    append_history(body.user_id, "assistant", answer)

    output_tokens = len(answer.split()) * 2
    usage = cost_guard.record_usage(body.user_id, estimated_input_tokens, output_tokens)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": body.user_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
        "cost_usd": usage["cost_usd"],
    }))

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/ask", tags=["Agent"])
def ask_requires_post(_api_key: str = Depends(verify_api_key)):
    raise HTTPException(status_code=405, detail="Use POST /ask with JSON body")


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready or _is_shutting_down:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        redis_client.ping()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis not ready: {exc}") from exc
    return {"ready": True, "redis": "ok", "in_flight_requests": _in_flight_requests}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


def _handle_signal(signum, _frame):
    global _is_ready, _is_shutting_down
    _is_ready = False
    _is_shutting_down = True
    logger.info(json.dumps({"event": "graceful shutdown signal", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=settings.graceful_shutdown_timeout_seconds,
    )
