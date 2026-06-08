from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from app.core.config import settings
from app.core.redis import close_redis, get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(title="AI Customer Support System", lifespan=lifespan)


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