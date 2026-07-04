"""Rate-limited CRM API client with retry logic and quota management."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from .crm_auth import OAuth2Client, OAuthToken

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when API quota is exceeded."""

    pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class RetryStrategy(str, Enum):
    """Retry strategies."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class QuotaStatus(str, Enum):
    """Quota status."""

    AVAILABLE = "available"
    LIMITED = "limited"
    EXCEEDED = "exceeded"


class QuotaInfo(BaseModel):
    """API quota information."""

    quota_limit: int = Field(description="Total quota limit")
    quota_remaining: int = Field(description="Remaining quota")
    quota_used: int = Field(description="Quota used")
    reset_time: Optional[datetime] = Field(default=None, description="Quota reset time")
    status: QuotaStatus = Field(description="Quota status")


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(
        self,
        max_requests: int = 100,
        time_window: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: list[float] = []

    async def acquire(self) -> None:
        """Acquire rate limit permit, waiting if necessary."""
        now = time.time()

        # Remove old requests outside time window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]

        # Check if limit reached
        if len(self.requests) >= self.max_requests:
            wait_time = self.time_window - (now - self.requests[0])
            logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            # Retry after waiting
            await self.acquire()
            return

        # Add current request
        self.requests.append(now)


class QuotaManager:
    """API quota manager."""

    def __init__(self, quota_limit: int = 10000):
        """
        Initialize quota manager.

        Args:
            quota_limit: Total quota limit
        """
        self.quota_limit = quota_limit
        self.quota_used = 0
        self.reset_time: Optional[datetime] = None
        self.request_queue: asyncio.Queue = asyncio.Queue()

    def get_quota_info(self) -> QuotaInfo:
        """
        Get current quota information.

        Returns:
            Quota information
        """
        quota_remaining = self.quota_limit - self.quota_used
        status = QuotaStatus.AVAILABLE

        if quota_remaining <= 0:
            status = QuotaStatus.EXCEEDED
        elif quota_remaining < self.quota_limit * 0.1:
            status = QuotaStatus.LIMITED

        return QuotaInfo(
            quota_limit=self.quota_limit,
            quota_remaining=max(0, quota_remaining),
            quota_used=self.quota_used,
            reset_time=self.reset_time,
            status=status,
        )

    def consume_quota(self, amount: int = 1) -> None:
        """
        Consume quota.

        Args:
            amount: Amount of quota to consume

        Raises:
            QuotaExceededError: If quota exceeded
        """
        quota_info = self.get_quota_info()

        if quota_info.status == QuotaStatus.EXCEEDED:
            raise QuotaExceededError(f"Quota exceeded: {quota_info.quota_used}/{quota_info.quota_limit}")

        self.quota_used += amount
        logger.info(f"Quota consumed: {amount}, remaining: {self.quota_limit - self.quota_used}")

    def reset_quota(self) -> None:
        """Reset quota."""
        self.quota_used = 0
        self.reset_time = datetime.now(UTC)
        logger.info("Quota reset")

    async def queue_request(self, request_func: Any) -> Any:
        """
        Queue request if quota is limited.

        Args:
            request_func: Request function to execute

        Returns:
            Request result
        """
        quota_info = self.get_quota_info()

        if quota_info.status == QuotaStatus.EXCEEDED:
            # Queue the request
            logger.info("Quota exceeded, queuing request")
            await self.request_queue.put(request_func)
            # Wait for quota reset
            while self.get_quota_info().status == QuotaStatus.EXCEEDED:
                await asyncio.sleep(1)
            # Execute queued request
            result = await request_func()
            return result
        else:
            # Execute immediately
            return await request_func()


class CRMClient:
    """Rate-limited CRM API client with retry logic."""

    def __init__(
        self,
        base_url: str,
        oauth_client: OAuth2Client,
        max_retries: int = 3,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        max_requests_per_minute: int = 100,
        quota_limit: int = 10000,
    ):
        """
        Initialize CRM client.

        Args:
            base_url: CRM API base URL
            oauth_client: OAuth 2.0 client
            max_retries: Maximum number of retries
            retry_strategy: Retry strategy
            max_requests_per_minute: Maximum requests per minute
            quota_limit: Total quota limit
        """
        self.base_url = base_url
        self.oauth_client = oauth_client
        self.max_retries = max_retries
        self.retry_strategy = retry_strategy
        self.rate_limiter = RateLimiter(max_requests=max_requests_per_minute, time_window=60)
        self.quota_manager = QuotaManager(quota_limit=quota_limit)
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay based on strategy.

        Args:
            attempt: Current attempt number

        Returns:
            Delay in seconds
        """
        if self.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return 2 ** attempt
        elif self.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            return attempt * 2
        else:  # FIXED_DELAY
            return 1.0

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic and rate limiting.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body data
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data

        Raises:
            Exception: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit permit
                await self.rate_limiter.acquire()

                # Consume quota
                self.quota_manager.consume_quota()

                # Get valid token
                token = await self.oauth_client.get_valid_token()

                # Prepare headers
                request_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                if headers:
                    request_headers.update(headers)

                # Make request
                response = await self.http_client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=request_headers,
                )

                # Check for rate limit errors
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                # Check for quota errors
                if response.status_code == 403:
                    quota_info = self.quota_manager.get_quota_info()
                    if quota_info.status == QuotaStatus.EXCEEDED:
                        logger.error("Quota exceeded")
                        raise QuotaExceededError("API quota exceeded")

                # Raise for other errors
                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")

                # Don't retry on client errors (4xx except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise

                # Calculate retry delay
                delay = await self._calculate_retry_delay(attempt)
                await asyncio.sleep(delay)

            except Exception as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")

                # Calculate retry delay
                delay = await self._calculate_retry_delay(attempt)
                await asyncio.sleep(delay)

        # All retries failed
        logger.error(f"Request failed after {self.max_retries} retries")
        raise last_exception if last_exception else Exception("Request failed")

    async def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response data
        """
        return await self._make_request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Make POST request.

        Args:
            endpoint: API endpoint
            data: Request body data

        Returns:
            Response data
        """
        return await self._make_request("POST", endpoint, data=data)

    async def put(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Make PUT request.

        Args:
            endpoint: API endpoint
            data: Request body data

        Returns:
            Response data
        """
        return await self._make_request("PUT", endpoint, data=data)

    async def delete(self, endpoint: str) -> dict[str, Any]:
        """
        Make DELETE request.

        Args:
            endpoint: API endpoint

        Returns:
            Response data
        """
        return await self._make_request("DELETE", endpoint)

    def get_quota_info(self) -> QuotaInfo:
        """
        Get current quota information.

        Returns:
            Quota information
        """
        return self.quota_manager.get_quota_info()

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
        await self.oauth_client.close()
