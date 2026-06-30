"""OAuth2 service for handling OAuth authentication flow."""

import json
import logging
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import jwt_service
from app.core.redis_client import redis_client
from app.models.auth_log import AuthLog
from app.models.oauth_account import OAuthAccount
from app.models.user import User

logger = logging.getLogger(__name__)


class OAuth2Service:
    """Service for OAuth2 authentication operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize OAuth服务.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def log_auth_attempt(
        self,
        auth_type: str,
        success: bool,
        user_id: Optional[UUID] = None,
        email: Optional[str] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Log OAuth authentication attempt.

        Args:
            auth_type: Type of authentication (oauth_login, oauth_link)
            success: Whether authentication was successful
            user_id: User ID
            email: User email
            failure_reason: Reason for failure
            ip_address: IP address
            user_agent: User agent string
            provider: OAuth provider
        """
        try:
            auth_log = AuthLog(
                user_id=user_id,
                email=email,
                auth_type=auth_type,
                success="success" if success else "failure",
                failure_reason=failure_reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.db.add(auth_log)
            await self.db.commit()

            self.logger.info(
                f"OAuth auth attempt logged: type={auth_type}, success={success}, "
                f"provider={provider}, user_id={user_id}, email={email}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log OAuth auth attempt: {e}")

    def map_oauth_user_info(
        self,
        provider: str,
        user_info: dict,
    ) -> dict:
        """
        Map OAuth user info to internal user model.

        Args:
            provider: OAuth provider (google, microsoft, github, slack)
            user_info: User info from OAuth provider

        Returns:
            Mapped user info dict
        """
        mapped = {
            "provider": provider,
            "provider_user_id": None,
            "email": None,
            "name": None,
            "avatar_url": None,
        }

        if provider == "google":
            mapped["provider_user_id"] = user_info.get("sub")
            mapped["email"] = user_info.get("email")
            mapped["name"] = user_info.get("name")
            mapped["avatar_url"] = user_info.get("picture")

        elif provider == "microsoft":
            mapped["provider_user_id"] = user_info.get("sub")
            mapped["email"] = user_info.get("email")
            mapped["name"] = user_info.get("name")
            mapped["avatar_url"] = None  # Microsoft doesn't provide avatar in basic scope

        elif provider == "github":
            mapped["provider_user_id"] = str(user_info.get("id"))
            mapped["email"] = user_info.get("email")
            mapped["name"] = user_info.get("name") or user_info.get("login")
            mapped["avatar_url"] = user_info.get("avatar_url")

        elif provider == "slack":
            user_data = user_info.get("user", {})
            mapped["provider_user_id"] = user_data.get("id")
            mapped["email"] = user_data.get("email")
            mapped["name"] = user_data.get("real_name") or user_data.get("name")
            mapped["avatar_url"] = user_data.get("image_512")

        return mapped

    async def find_or_create_user(
        self,
        provider: str,
        mapped_user_info: dict,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        raw_user_data: Optional[dict] = None,
    ) -> Tuple[User, bool]:
        """
        Find existing user or create new user from OAuth info.

        Args:
            provider: OAuth provider
            mapped_user_info: Mapped user info
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expires_at: Token expiration time
            raw_user_data: Raw user data from provider

        Returns:
            Tuple of (user, is_new_user)
        """
        provider_user_id = mapped_user_info["provider_user_id"]
        email = mapped_user_info["email"]

        # Check if OAuth account already exists
        oauth_query = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        oauth_result = await self.db.execute(oauth_query)
        oauth_account = oauth_result.scalar_one_or_none()

        if oauth_account:
            # Update OAuth account with new tokens
            oauth_account.access_token = access_token
            oauth_account.refresh_token = refresh_token
            oauth_account.token_expires_at = token_expires_at
            oauth_account.raw_user_data = json.dumps(raw_user_data) if raw_user_data else None
            oauth_account.updated_at = datetime.utcnow()

            # Get user
            user_query = select(User).where(User.id == oauth_account.user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if user:
                await self.db.commit()
                self.logger.info(f"Existing user found via OAuth: {email}")
                return user, False

        # Check if user exists with same email (account linking)
        if email:
            user_query = select(User).where(User.email == email)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if user:
                # Link OAuth account to existing user
                oauth_account = OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
                    email=email,
                    name=mapped_user_info["name"],
                    avatar_url=mapped_user_info["avatar_url"],
                    raw_user_data=json.dumps(raw_user_data) if raw_user_data else None,
                )

                self.db.add(oauth_account)
                await self.db.commit()

                self.logger.info(f"OAuth account linked to existing user: {email}")
                return user, False

        # Create new user
        user = User(
            id=uuid4(),
            email=email or f"{provider}_{provider_user_id}@oauth.local",
            name=mapped_user_info["name"] or "OAuth User",
            role="user",
            is_active=True,
            is_verified=True,  # OAuth users are pre-verified
            auth_provider=provider,
        )

        self.db.add(user)
        await self.db.flush()  # Get user ID

        # Create OAuth account
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            email=email,
            name=mapped_user_info["name"],
            avatar_url=mapped_user_info["avatar_url"],
            raw_user_data=json.dumps(raw_user_data) if raw_user_data else None,
        )

        self.db.add(oauth_account)
        await self.db.commit()

        self.logger.info(f"New user created via OAuth: {email}")
        return user, True

    async def handle_oauth_callback(
        self,
        provider: str,
        user_info: dict,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Tuple[User, str, str]]:
        """
        Handle OAuth callback and issue JWT tokens.

        Args:
            provider: OAuth provider
            user_info: User info from OAuth provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expires_at: Token expiration time
            ip_address: IP address
            user_agent: User agent

        Returns:
            Tuple of (user, access_token, refresh_token) or None if failed
        """
        try:
            # Map user info
            mapped_user_info = self.map_oauth_user_info(provider, user_info)

            # Find or create user
            user, is_new_user = await self.find_or_create_user(
                provider=provider,
                mapped_user_info=mapped_user_info,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                raw_user_data=user_info,
            )

            # Generate JWT tokens
            jwt_access_token = jwt_service.create_access_token(
                user_id=user.id,
                email=user.email,
                role=user.role,
            )

            jwt_refresh_token = jwt_service.create_refresh_token(
                user_id=user.id,
                email=user.email,
            )

            # Store refresh token in Redis
            redis_client.store_refresh_token(str(user.id), jwt_refresh_token)

            # Log successful OAuth login
            await self.log_auth_attempt(
                auth_type="oauth_login",
                success=True,
                user_id=user.id,
                email=user.email,
                ip_address=ip_address,
                user_agent=user_agent,
                provider=provider,
            )

            self.logger.info(
                f"OAuth login successful: provider={provider}, "
                f"user_id={user.id}, email={user.email}, new_user={is_new_user}"
            )

            return user, jwt_access_token, jwt_refresh_token

        except Exception as e:
            self.logger.error(f"Error handling OAuth callback: {e}")
            await self.log_auth_attempt(
                auth_type="oauth_login",
                success=False,
                email=user_info.get("email"),
                failure_reason=str(e),
                ip_address=ip_address,
                user_agent=user_agent,
                provider=provider,
            )
            return None

    async def link_oauth_account(
        self,
        user_id: UUID,
        provider: str,
        user_info: dict,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> bool:
        """
        Link OAuth account to existing user.

        Args:
            user_id: User ID
            provider: OAuth provider
            user_info: User info from OAuth provider
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expires_at: Token expiration time

        Returns:
            True if successful, False otherwise
        """
        try:
            # Map user info
            mapped_user_info = self.map_oauth_user_info(provider, user_info)
            provider_user_id = mapped_user_info["provider_user_id"]

            # Check if OAuth account already exists
            oauth_query = select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
            oauth_result = await self.db.execute(oauth_query)
            existing_oauth = oauth_result.scalar_one_or_none()

            if existing_oauth:
                if existing_oauth.user_id != user_id:
                    self.logger.warning(
                        f"OAuth account already linked to different user: "
                        f"provider={provider}, provider_user_id={provider_user_id}"
                    )
                    return False

                # Update existing
                existing_oauth.access_token = access_token
                existing_oauth.refresh_token = refresh_token
                existing_oauth.token_expires_at = token_expires_at
                existing_oauth.updated_at = datetime.utcnow()
            else:
                # Create new OAuth account
                oauth_account = OAuthAccount(
                    user_id=user_id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
                    email=mapped_user_info["email"],
                    name=mapped_user_info["name"],
                    avatar_url=mapped_user_info["avatar_url"],
                    raw_user_data=json.dumps(user_info),
                )

                self.db.add(oauth_account)

            await self.db.commit()

            self.logger.info(f"OAuth account linked: provider={provider}, user_id={user_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error linking OAuth account: {e}")
            return False

    async def get_user_oauth_accounts(self, user_id: UUID) -> list[OAuthAccount]:
        """
        Get all OAuth accounts linked to a user.

        Args:
            user_id: User ID

        Returns:
            List of OAuth accounts
        """
        query = select(OAuthAccount).where(OAuthAccount.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def unlink_oauth_account(self, user_id: UUID, provider: str) -> bool:
        """
        Unlink OAuth account from user.

        Args:
            user_id: User ID
            provider: OAuth provider

        Returns:
            True if successful, False otherwise
        """
        try:
            query = select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
            result = await self.db.execute(query)
            oauth_account = result.scalar_one_or_none()

            if oauth_account:
                await self.db.delete(oauth_account)
                await self.db.commit()

                self.logger.info(f"OAuth account unlinked: provider={provider}, user_id={user_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error unlinking OAuth account: {e}")
            return False
