"""Authentication dependencies for FastAPI."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.jwt import jwt_service
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Get current user from JWT token.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User data from token

    Raises:
        HTTPException: If token is invalid or blacklisted
    """
    token = credentials.credentials

    # Check if token is blacklisted
    if redis_client.is_blacklisted(token):
        logger.warning("Attempt to use blacklisted token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = jwt_service.verify_token(token, token_type="access")

    if not payload:
        logger.warning("Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[dict]:
    """
    Get current user from JWT token (optional).

    Args:
        credentials: HTTP authorization credentials (optional)

    Returns:
        User data from token or None if not authenticated
    """
    if not credentials:
        return None

    token = credentials.credentials

    # Check if token is blacklisted
    if redis_client.is_blacklisted(token):
        return None

    # Verify token
    payload = jwt_service.verify_token(token, token_type="access")

    return payload if payload else None


async def require_role(required_role: str):
    """
    Require specific role for access.

    Args:
        required_role: Required role

    Returns:
        Dependency function that checks role

    Raises:
        HTTPException: If user doesn't have required role
    """

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")

        if user_role != required_role and user_role != "admin":
            logger.warning(
                f"User {current_user.get('sub')} attempted to access "
                f"{required_role}-only resource with role {user_role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )

        return current_user

    return role_checker


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Require admin role for access.

    Args:
        current_user: Current user from token

    Returns:
        Current user

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.get("role") != "admin":
        logger.warning(
            f"User {current_user.get('sub')} attempted to access admin-only resource"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
