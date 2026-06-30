"""JWT authentication service."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# JWT configuration
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTService:
    """Service for JWT token operations."""

    def __init__(self):
        """Initialize JWT service."""
        self.secret_key = settings.SECRET_KEY
        self.algorithm = ALGORITHM
        self.logger = logger

    def create_access_token(
        self,
        user_id: UUID,
        email: str,
        role: str,
        additional_claims: Optional[dict] = None,
    ) -> str:
        """
        Create an access token.

        Args:
            user_id: User ID
            email: User email
            role: User role
            additional_claims: Additional claims to include

        Returns:
            JWT access token
        """
        now = datetime.utcnow()
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "access",
            "iat": now.timestamp(),
            "exp": expire.timestamp(),
        }

        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        self.logger.info(f"Access token created for user {user_id}")

        return encoded_jwt

    def create_refresh_token(
        self,
        user_id: UUID,
        email: str,
        additional_claims: Optional[dict] = None,
    ) -> str:
        """
        Create a refresh token.

        Args:
            user_id: User ID
            email: User email
            additional_claims: Additional claims to include

        Returns:
            JWT refresh token
        """
        now = datetime.utcnow()
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "sub": str(user_id),
            "email": email,
            "type": "refresh",
            "iat": now.timestamp(),
            "exp": expire.timestamp(),
        }

        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        self.logger.info(f"Refresh token created for user {user_id}")

        return encoded_jwt

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {e}")
            return None

    def verify_token(self, token: str, token_type: str = "access") -> Optional[dict]:
        """
        Verify a JWT token and check its type.

        Args:
            token: JWT token
            token_type: Expected token type (access or refresh)

        Returns:
            Decoded token payload or None if invalid
        """
        payload = self.decode_token(token)

        if not payload:
            return None

        # Check token type
        if payload.get("type") != token_type:
            self.logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
            return None

        return payload

    def get_user_id_from_token(self, token: str) -> Optional[UUID]:
        """
        Extract user ID from token.

        Args:
            token: JWT token

        Returns:
            User ID or None if invalid
        """
        payload = self.decode_token(token)

        if not payload:
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        try:
            return UUID(user_id_str)
        except ValueError:
            self.logger.warning(f"Invalid user ID in token: {user_id_str}")
            return None

    def hash_password(self, password: str) -> str:
        """
        Hash a password.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)


# Global JWT service instance
jwt_service = JWTService()
