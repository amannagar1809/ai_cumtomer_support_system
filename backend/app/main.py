from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.deps import get_client_ip
from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.rate_limit_handlers import rate_limit_exception_handler
from app.core.redis import close_redis, get_redis_client
from app.services.rate_limiter import RateLimiterService


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


class IpRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce rate_limit:{ip}:requests — 1000 req/min per IP."""

    SKIP_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        limiter = RateLimiterService()
        try:
            await limiter.enforce_ip_request(get_client_ip(request))
        except RateLimitExceeded as exc:
            return rate_limit_exception_handler(request, exc)
        return await call_next(request)


app = FastAPI(title="AI Customer Support System", lifespan=lifespan)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(IpRateLimitMiddleware)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    checks: dict[str, str] = {}
    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"not-ready: {type(e).__name__}"
    try:
        conn = await asyncpg.connect(
            settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
            timeout=2,
        )
        await conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"not-ready: {type(e).__name__}"
    overall = "ok" if all(v == "ok" for v in checks.values()) else "not-ready"
    return {"status": overall, "checks": checks}