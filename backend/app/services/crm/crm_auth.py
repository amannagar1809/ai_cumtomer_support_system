"""CRM OAuth 2.0 authentication module."""

import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OAuthToken(BaseModel):
    """OAuth 2.0 token model."""

    access_token: str = Field(description="Access token")
    refresh_token: Optional[str] = Field(default=None, description="Refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    scope: Optional[str] = Field(default=None, description="Token scope")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Token issuance timestamp")

    @property
    def expires_at(self) -> datetime:
        """Calculate token expiration timestamp."""
        return self.issued_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now(UTC) >= self.expires_at

    @property
    def expires_soon(self) -> bool:
        """Check if token expires soon (within 5 minutes)."""
        return datetime.now(UTC) >= self.expires_at - timedelta(minutes=5)


class OAuthConfig(BaseModel):
    """OAuth 2.0 configuration."""

    client_id: str = Field(description="OAuth client ID")
    client_secret: str = Field(description="OAuth client secret")
    redirect_uri: str = Field(description="OAuth redirect URI")
    auth_url: str = Field(description="Authorization URL")
    token_url: str = Field(description="Token URL")
    scope: Optional[str] = Field(default=None, description="OAuth scope")
    state: Optional[str] = Field(default=None, description="OAuth state parameter")


class OAuth2Client:
    """OAuth 2.0 client for CRM authentication."""

    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth 2.0 client.

        Args:
            config: OAuth configuration
        """
        self.config = config
        self.token: Optional[OAuthToken] = None
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def generate_auth_url(self) -> str:
        """
        Generate authorization URL.

        Returns:
            Authorization URL
        """
        state = secrets.token_urlsafe(32)
        self.config.state = state

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "state": state,
        }

        if self.config.scope:
            params["scope"] = self.config.scope

        auth_url = f"{self.config.auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        logger.info(f"Generated auth URL with state: {state}")
        return auth_url

    async def exchange_code_for_token(self, code: str, state: str) -> OAuthToken:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            state: State parameter for verification

        Returns:
            OAuth token

        Raises:
            ValueError: If state doesn't match
        """
        if state != self.config.state:
            raise ValueError("Invalid state parameter")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "redirect_uri": self.config.redirect_uri,
        }

        response = await self.http_client.post(self.config.token_url, data=data)
        response.raise_for_status()

        token_data = response.json()

        self.token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data["expires_in"],
            scope=token_data.get("scope"),
        )

        logger.info(f"Successfully exchanged code for token, expires at: {self.token.expires_at}")
        return self.token

    async def refresh_access_token(self) -> OAuthToken:
        """
        Refresh access token using refresh token.

        Returns:
            New OAuth token

        Raises:
            ValueError: If no refresh token available
        """
        if not self.token or not self.token.refresh_token:
            raise ValueError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.token.refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        response = await self.http_client.post(self.config.token_url, data=data)
        response.raise_for_status()

        token_data = response.json()

        self.token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", self.token.refresh_token),
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data["expires_in"],
            scope=token_data.get("scope"),
        )

        logger.info(f"Successfully refreshed token, expires at: {self.token.expires_at}")
        return self.token

    async def get_valid_token(self) -> str:
        """
        Get valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            ValueError: If no token available
        """
        if not self.token:
            raise ValueError("No token available, please authenticate first")

        if self.token.is_expired:
            if self.token.refresh_token:
                await self.refresh_access_token()
            else:
                raise ValueError("Token expired and no refresh token available")

        elif self.token.expires_soon:
            if self.token.refresh_token:
                await self.refresh_access_token()

        return self.token.access_token

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
