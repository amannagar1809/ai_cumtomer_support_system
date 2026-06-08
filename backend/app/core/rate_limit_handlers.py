from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import RateLimitExceeded
from app.schemas.rate_limit import RateLimitErrorBody, RateLimitErrorDetails, RateLimitErrorResponse


def rate_limit_exception_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID")
    body = RateLimitErrorResponse(
        error=RateLimitErrorBody(
            code="RATE_LIMITED",
            message=exc.message,
            request_id=request_id,
            details=RateLimitErrorDetails(
                limit=exc.limit,
                window=f"{exc.window_seconds // 60} minute"
                if exc.window_seconds >= 60
                else f"{exc.window_seconds} seconds",
                retry_after_seconds=exc.retry_after_seconds,
                remaining=exc.remaining,
                scope=exc.scope,
            ),
        )
    )
    return JSONResponse(
        status_code=429,
        content=body.model_dump(),
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )
