"""Authentication schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request for user login."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Response for successful login."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user_id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    role: str = Field(..., description="User role")


class RefreshTokenRequest(BaseModel):
    """Request for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Response for token refresh."""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class LogoutRequest(BaseModel):
    """Request for logout."""

    refresh_token: Optional[str] = Field(default=None, description="Refresh token to revoke")


class LogoutResponse(BaseModel):
    """Response for logout."""

    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Status message")


class TokenValidationResponse(BaseModel):
    """Response for token validation."""

    valid: bool = Field(..., description="Whether token is valid")
    user_id: Optional[UUID] = Field(default=None, description="User ID if valid")
    email: Optional[str] = Field(default=None, description="User email if valid")
    role: Optional[str] = Field(default=None, description="User role if valid")
