"""OAuth schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OAuthLoginResponse(BaseModel):
    """Response for OAuth login."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user_id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    provider: str = Field(..., description="OAuth provider")
    is_new_user: bool = Field(..., description="Whether this is a new user")


class OAuthAccountInfo(BaseModel):
    """OAuth account information."""

    id: UUID = Field(..., description="OAuth account ID")
    provider: str = Field(..., description="OAuth provider")
    email: Optional[str] = Field(default=None, description="Email from provider")
    name: Optional[str] = Field(default=None, description="Name from provider")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    created_at: str = Field(..., description="Account creation timestamp")


class LinkedAccountsResponse(BaseModel):
    """Response for linked accounts."""

    user_id: UUID = Field(..., description="User ID")
    oauth_accounts: list[OAuthAccountInfo] = Field(..., description="Linked OAuth accounts")


class LinkOAuthAccountRequest(BaseModel):
    """Request to link OAuth account."""

    provider: str = Field(..., description="OAuth provider")
    authorization_code: str = Field(..., description="Authorization code from OAuth flow")


class LinkOAuthAccountResponse(BaseModel):
    """Response for linking OAuth account."""

    success: bool = Field(..., description="Whether linking was successful")
    message: str = Field(..., description="Status message")
    account: Optional[OAuthAccountInfo] = Field(default=None, description="Linked account info")


class UnlinkOAuthAccountResponse(BaseModel):
    """Response for unlinking OAuth account."""

    success: bool = Field(..., description="Whether unlinking was successful")
    message: str = Field(..., description="Status message")
