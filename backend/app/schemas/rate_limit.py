from pydantic import BaseModel, Field


class RateLimitErrorDetails(BaseModel):
    limit: int
    window: str
    retry_after_seconds: int
    remaining: float
    scope: str


class RateLimitErrorBody(BaseModel):
    code: str = "RATE_LIMITED"
    message: str
    request_id: str | None = None
    details: RateLimitErrorDetails


class RateLimitErrorResponse(BaseModel):
    error: RateLimitErrorBody


class RateLimitStatus(BaseModel):
    allowed: bool
    remaining: float
    limit: int
    retry_after_seconds: int = 0
