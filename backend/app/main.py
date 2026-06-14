import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.deps import get_client_ip
from app.api.ws.chat import router as chat_ws_router
from app.api.v1.chat import router as chat_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.uploads import router as uploads_router
from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.rate_limit_handlers import rate_limit_exception_handler
from app.core.redis import close_redis, get_redis_client
from app.services.chat_websocket import get_chat_connection_manager
from app.services.message_queue import MessageQueueService
from app.services.rate_limiter import RateLimiterService
from app.services.session_cache import SessionCacheService

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
logger = logging.getLogger(__name__)


async def _session_cleanup_loop() -> None:
    service = SessionCacheService()
    while True:
        await asyncio.sleep(settings.session_cleanup_interval_seconds)
        try:
            deleted = await service.cleanup_expired_sessions()
            if deleted:
                logger.info("Cleaned up %s expired chat sessions", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Session cleanup job failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue = MessageQueueService()
    await queue.ensure_streams()
    cleanup_task = asyncio.create_task(
        _session_cleanup_loop(),
        name="session-cleanup",
    )
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await get_chat_connection_manager().close_all()
        await close_redis()


class IpRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce rate_limit:{ip}:requests - 1000 req/min per IP."""

    SKIP_PATHS = {
        "/health",
        "/health/ready",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/",
        "/static",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in self.SKIP_PATHS
            or path.startswith("/static")
            or path.startswith("/ws/")
        ):
            return await call_next(request)
        limiter = RateLimiterService()
        try:
            await limiter.enforce_ip_request(get_client_ip(request))
        except RateLimitExceeded as exc:
            return rate_limit_exception_handler(request, exc)
        return await call_next(request)


app = FastAPI(title="AI Customer Support System", lifespan=lifespan)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(IpRateLimitMiddleware)
app.include_router(chat_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(chat_ws_router)

if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
async def serve_chat_page():
    index = _FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "AI Customer Support API", "docs": "/docs"}


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
