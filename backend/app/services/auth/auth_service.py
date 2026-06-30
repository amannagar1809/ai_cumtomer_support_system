"""Authentication service for login, logout, and token management."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import jwt_service
from app.core.redis_client import redis_client
from app.models.auth_log import AuthLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize auth service.

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
        token_type: Optional[str] = None,
    ):
        """
        Log authentication attempt.

        Args:
            auth_type: Type of authentication (login, logout, refresh, token_validation)
            success: Whether authentication was successful
            user_id: User ID
            email: User email
            failure_reason: Reason for failure
            ip_address: IP address
            user_agent: User agent string
            token_type: Token type (access, refresh)
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
                token_type=token_type,
            )

            self.db.add(auth_log)
            await self.db.commit()

            self.logger.info(
                f"Auth attempt logged: type={auth_type}, success={success}, "
                f"user_id={user_id}, email={email}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log auth attempt: {e}")

    async def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[tuple[User, str, str]]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password
            ip_address: IP address
            user_agent: User agent

        Returns:
            Tuple of (user, access_token, refresh_token) or None if authentication fails
        """
        # Find user by email
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            await self.log_auth_attempt(
                auth_type="login",
                success=False,
                email=email,
                failure_reason="user_not_found",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.logger.warning(f"Login attempt for non-existent user: {email}")
            return None

        # Verify password
        if not jwt_service.verify_password(password, user.hashed_password):
            await self.log_auth_attempt(
                auth_type="login",
                success=False,
                user_id=user.id,
                email=email,
                failure_reason="invalid_credentials",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.logger.warning(f"Failed login attempt for user: {email}")
            return None

        # Check if user is active
        if not user.is_active:
            await self.log_auth_attempt(
                auth_type="login",
                success=False,
                user_id=user.id,
                email=email,
                failure_reason="account_inactive",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.logger.warning(f"Login attempt for inactive user: {email}")
            return None

        # Generate tokens
        access_token = jwt_service.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )

        refresh_token = jwt_service.create_refresh_token(
            user_id=user.id,
            email=user.email,
        )

        # Store refresh token in Redis
        redis_client.store_refresh_token(str(user.id), refresh_token)

        # Log successful login
        await self.log_auth_attempt(
            auth_type="login",
            success=True,
            user_id=user.id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            token_type="access",
        )

        self.logger.info(f"User logged in successfully: {email}")

        return user, access_token, refresh_token

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[tuple[str, str]]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token
            ip_address: IP address
            user_agent: User agent

        Returns:
            Tuple of (new_access_token, new_refresh_token) or None if refresh fails
        """
        # Verify refresh token
        payload = jwt_service.verify_token(refresh_token, token_type="refresh")

        if not payload:
            await self.log_auth_attempt(
                auth_type="refresh",
                success=False,
                failure_reason="invalid_refresh_token",
                ip_address=ip_address,
                user_agent=user_agent,
                token_type="refresh",
            )
            self.logger.warning("Invalid refresh token")
            return None

        user_id_str = payload.get("sub")
        email = payload.get("email")

        # Check if refresh token exists in Redis
        stored_token = redis_client.get_refresh_token(user_id_str)

        if not stored_token or stored_token != refresh_token:
            await self.log_auth_attempt(
                auth_type="refresh",
                success=False,
                user_id=UUID(user_id_str) if user_id_str else None,
                email=email,
                failure_reason="refresh_token_not_found_or_mismatch",
                ip_address=ip_address,
                user_agent=user_agent,
                token_type="refresh",
            )
            self.logger.warning("Refresh token not found or mismatched")
            return None

        # Get user from database
        try:
            user_id = UUID(user_id_str)
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if not user or not user.is_active:
                await self.log_auth_attempt(
                    auth_type="refresh",
                    success=False,
                    user_id=user_id,
                    email=email,
                    failure_reason="user_not_found_or_inactive",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    token_type="refresh",
                )
                return None

            # Generate new tokens
            new_access_token = jwt_service.create_access_token(
                user_id=user.id,
                email=user.email,
                role=user.role,
            )

            new_refresh_token = jwt_service.create_refresh_token(
                user_id=user.id,
                email=user.email,
            )

            # Store new refresh token in Redis
            redis_client.store_refresh_token(str(user.id), new_refresh_token)

            # Log successful refresh
            await self.log_auth_attempt(
                auth_type="refresh",
                success=True,
                user_id=user.id,
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
                token_type="refresh",
            )

            self.logger.info(f"Token refreshed successfully for user: {email}")

            return new_access_token, new_refresh_token

        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            await self.log_auth_attempt(
                auth_type="refresh",
                success=False,
                user_id=UUID(user_id_str) if user_id_str else None,
                email=email,
                failure_reason="server_error",
                ip_address=ip_address,
                user_agent=user_agent,
                token_type="refresh",
            )
            return None

    async def logout(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Logout user by blacklisting tokens.

        Args:
            access_token: Access token to blacklist
            refresh_token: Refresh token to delete (optional)
            ip_address: IP address
            user_agent: User agent

        Returns:
            True if logout successful, False otherwise
        """
        try:
            # Get user info from token
            payload = jwt_service.decode_token(access_token)

            if payload:
                user_id = payload.get("sub")
                email = payload.get("email")

                # Blacklist access token
                redis_client.add_to_blacklist(access_token)

                # Delete refresh token if provided
                if refresh_token:
                    redis_client.delete_refresh_token(user_id)

                # Log logout
                await self.log_auth_attempt(
                    auth_type="logout",
                    success=True,
                    user_id=UUID(user_id) if user_id else None,
                    email=email,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    token_type="access",
                )

                self.logger.info(f"User logged out: {email}")

                return True
            else:
                await self.log_auth_attempt(
                    auth_type="logout",
                    success=False,
                    failure_reason="invalid_token",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    token_type="access",
                )
                return False

        except Exception as e:
            self.logger.error(f"Error during logout: {e}")
            return False
