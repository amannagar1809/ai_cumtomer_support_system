from uuid import UUID

from fastapi import Request

from app.services.rate_limiter import RateLimiterService


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def enforce_ip_rate_limit(request: Request) -> None:
    limiter = RateLimiterService()
    await limiter.enforce_ip_request(get_client_ip(request))


async def enforce_user_message_rate_limit(user_id: UUID) -> None:
    limiter = RateLimiterService()
    await limiter.enforce_user_message(user_id)
