"""Rate limiting middleware for FastAPI."""

import logging
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.rate_limiter import (
    RateLimitConfig,
    rate_limiter,
    rate_limit_tracker,
)

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI."""

    def __init__(self):
        """Initialize rate limit middleware."""
        self.limiter = rate_limiter
        self.tracker = rate_limit_tracker
        self.config = RateLimitConfig()
        self.logger = logger

    def is_whitelisted(self, ip_address: str) -> bool:
        """
        Check if IP address is whitelisted from rate limiting.

        Args:
            ip_address: IP address to check

        Returns:
            True if whitelisted, False otherwise
        """
        if not hasattr(settings, 'rate_limit_whitelist'):
            return False

        whitelist = settings.rate_limit_whitelist or []
        return ip_address in whitelist

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        """
        Check rate limit for a key.

        Args:
            key: Unique identifier
            limit: Maximum requests
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after)
        """
        is_allowed, retry_after = await self.limiter.is_allowed(key, limit, window)

        if not is_allowed:
            # Record hit for alerting
            self.tracker.record_hit(key)
        else:
            # Record success
            self.tracker.record_success(key)

        return is_allowed, retry_after

    async def __call__(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint

        Returns:
            Response
        """
        try:
            # Get client IP
            ip_address = request.client.host if request.client else "unknown"

            # Check whitelist
            if self.is_whitelisted(ip_address):
                self.logger.debug(f"IP {ip_address} is whitelisted from rate limiting")
                return await call_next(request)

            # Get user ID if authenticated
            user_id = None
            auth_header = request.headers.get("authorization")
            if auth_header:
                # Extract user ID from JWT token if available
                # This is a simplified check - in production, verify the token
                try:
                    from app.core.jwt import jwt_service
                    token = auth_header.replace("Bearer ", "")
                    payload = jwt_service.verify_token(token, token_type="access")
                    if payload:
                        user_id = payload.get("sub")
                except Exception:
                    pass

            # Determine rate limit based on endpoint type
            path = request.url.path

            # Auth endpoints have stricter limits
            if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/refresh"):
                limit = self.config.AUTH_PER_MINUTE
                window = 60
                key = f"auth:{ip_address}"
            elif user_id:
                # Authenticated user limits
                limit = self.config.USER_PER_MINUTE
                window = 60
                key = f"user:{user_id}"
            else:
                # IP-based limits for unauthenticated requests
                limit = self.config.IP_PER_MINUTE
                window = 60
                key = f"ip:{ip_address}"

            # Check rate limit
            is_allowed, retry_after = await self.check_rate_limit(key, limit, window)

            if not is_allowed:
                self.logger.warning(
                    f"Rate limit exceeded for {key}: {limit} requests per {window}s, "
                    f"retry after {retry_after}s"
                )

                # Return 429 with Retry-After header
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Window": str(window),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            current_count = await self.limiter.get_current_count(key, window)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
            response.headers["X-RateLimit-Window"] = str(window)

            return response

        except Exception as e:
            self.logger.error(f"Rate limiting middleware error: {e}")
            # Fail open - allow request if middleware fails
            return await call_next(request)


def rate_limit_middleware() -> RateLimitMiddleware:
    """
    Get rate limit middleware instance.

    Returns:
        Rate limit middleware instance
    """
    return RateLimitMiddleware()


# Decorator for per-endpoint rate limiting
def rate_limit(limit: int, window: int, key_func: Optional[Callable] = None):
    """
    Decorator for per-endpoint rate limiting.

    Args:
        limit: Maximum requests
        window: Time window in seconds
        key_func: Function to generate rate limit key from request

    Returns:
        Decorator function
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request = kwargs.get("request")

            if not request:
                return await func(*args, **kwargs)

            # Generate key
            if key_func:
                key = key_func(request)
            else:
                ip_address = request.client.host if request.client else "unknown"
                key = f"endpoint:{request.url.path}:{ip_address}"

            # Check rate limit
            is_allowed, retry_after = await rate_limiter.is_allowed(key, limit, window)

            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
