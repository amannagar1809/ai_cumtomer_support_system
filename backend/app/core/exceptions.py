class RateLimitExceeded(Exception):
    """Raised when token bucket denies a request."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        retry_after_seconds: int,
        remaining: float,
        scope: str,
        message: str,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after_seconds = retry_after_seconds
        self.remaining = remaining
        self.scope = scope
        self.message = message
        super().__init__(message)
