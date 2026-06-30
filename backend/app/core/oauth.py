"""OAuth2 configuration and service."""

import logging
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)


class OAuthProvider:
    """OAuth provider configuration."""

    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        server_metadata_url: Optional[str] = None,
        authorize_url: Optional[str] = None,
        access_token_url: Optional[str] = None,
        userinfo_url: Optional[str] = None,
        scope: Optional[str] = None,
    ):
        """
        Initialize OAuth provider.

        Args:
            name: Provider name (google, microsoft, github, slack)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            server_metadata_url: OpenID Connect discovery URL
            authorize_url: Authorization endpoint URL
            access_token_url: Token endpoint URL
            userinfo_url: User info endpoint URL
            scope: OAuth scope
        """
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.server_metadata_url = server_metadata_url
        self.authorize_url = authorize_url
        self.access_token_url = access_token_url
        self.userinfo_url = userinfo_url
        self.scope = scope


class OAuthService:
    """Service for OAuth2 operations."""

    def __init__(self):
        """Initialize OAuth service."""
        self.oauth = OAuth()
        self.providers = {}
        self._register_providers()
        self.logger = logger

    def _register_providers(self):
        """Register OAuth providers from configuration."""
        # Google OAuth2
        if settings.google_oauth_client_id and settings.google_oauth_client_secret:
            self.oauth.register(
                name="google",
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={
                    "scope": "openid email profile",
                },
            )
            self.providers["google"] = True
            self.logger.info("Google OAuth2 provider registered")

        # Microsoft OAuth2
        if settings.microsoft_oauth_client_id and settings.microsoft_oauth_client_secret:
            self.oauth.register(
                name="microsoft",
                client_id=settings.microsoft_oauth_client_id,
                client_secret=settings.microsoft_oauth_client_secret,
                server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
                client_kwargs={
                    "scope": "openid email profile",
                },
            )
            self.providers["microsoft"] = True
            self.logger.info("Microsoft OAuth2 provider registered")

        # GitHub OAuth2
        if settings.github_oauth_client_id and settings.github_oauth_client_secret:
            self.oauth.register(
                name="github",
                client_id=settings.github_oauth_client_id,
                client_secret=settings.github_oauth_client_secret,
                authorize_url="https://github.com/login/oauth/authorize",
                access_token_url="https://github.com/login/oauth/access_token",
                userinfo_url="https://api.github.com/user",
                client_kwargs={
                    "scope": "user:email",
                },
            )
            self.providers["github"] = True
            self.logger.info("GitHub OAuth2 provider registered")

        # Slack OAuth2
        if settings.slack_oauth_client_id and settings.slack_oauth_client_secret:
            self.oauth.register(
                name="slack",
                client_id=settings.slack_oauth_client_id,
                client_secret=settings.slack_oauth_client_secret,
                authorize_url="https://slack.com/oauth/v2/authorize",
                access_token_url="https://slack.com/api/oauth.v2.access",
                userinfo_url="https://slack.com/api/users.info",
                client_kwargs={
                    "scope": "openid email profile",
                },
            )
            self.providers["slack"] = True
            self.logger.info("Slack OAuth2 provider registered")

    def is_provider_enabled(self, provider: str) -> bool:
        """
        Check if OAuth provider is enabled.

        Args:
            provider: Provider name

        Returns:
            True if enabled, False otherwise
        """
        return self.providers.get(provider, False)

    def get_client(self, provider: str):
        """
        Get OAuth client for provider.

        Args:
            provider: Provider name

        Returns:
            OAuth client or None if not enabled
        """
        if not self.is_provider_enabled(provider):
            self.logger.warning(f"OAuth provider {provider} is not enabled")
            return None

        return self.oauth.create_client(provider)


# Global OAuth service instance
oauth_service = OAuthService()
