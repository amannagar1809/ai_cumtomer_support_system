"""Authentication dependencies for FastAPI."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.jwt import jwt_service
from app.core.rbac import has_permission
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def log_authorization_failure(
    user_id: Optional[str],
    required_permission: str,
    user_role: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
):
    """
    Log authorization failure.

    Args:
        user_id: User ID
        required_permission: Required permission
        user_role: User's role
        ip_address: IP address
        user_agent: User agent
    """
    logger.warning(
        f"Authorization failure: user_id={user_id}, "
        f"required_permission={required_permission}, user_role={user_role}, "
        f"ip_address={ip_address}"
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> dict:
    """
    Get current user from JWT token.

    Args:
        credentials: HTTP authorization credentials
        request: FastAPI request

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


async def require_permission(required_permission: str):
    """
    Require specific permission for access.

    Args:
        required_permission: Required permission

    Returns:
        Dependency function that checks permission

    Raises:
        HTTPException: If user doesn't have required permission
    """

    async def permission_checker(
        current_user: dict = Depends(get_current_user),
        request: Request = None,
    ) -> dict:
        user_role = current_user.get("role")
        user_id = current_user.get("sub")

        # Check permission
        if not has_permission(user_role, required_permission):
            # Log authorization failure
            ip_address = request.client.host if request and request.client else None
            user_agent = request.headers.get("user-agent") if request else None

            await log_authorization_failure(
                user_id=str(user_id) if user_id else None,
                required_permission=required_permission,
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required permission: {required_permission}",
            )

        return current_user

    return permission_checker


async def require_any_permission(required_permissions: list[str]):
    """
    Require any of the specified permissions for access.

    Args:
        required_permissions: List of required permissions

    Returns:
        Dependency function that checks permissions

    Raises:
        HTTPException: If user doesn't have any of the required permissions
    """

    async def permission_checker(
        current_user: dict = Depends(get_current_user),
        request: Request = None,
    ) -> dict:
        from app.core.rbac import has_any_permission

        user_role = current_user.get("role")
        user_id = current_user.get("sub")

        # Check permissions
        if not has_any_permission(user_role, required_permissions):
            # Log authorization failure
            ip_address = request.client.host if request and request.client else None
            user_agent = request.headers.get("user-agent") if request else None

            await log_authorization_failure(
                user_id=str(user_id) if user_id else None,
                required_permission=f"any of {required_permissions}",
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {', '.join(required_permissions)}",
            )

        return current_user

    return permission_checker


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

    async def role_checker(
        current_user: dict = Depends(get_current_user),
        request: Request = None,
    ) -> dict:
        user_role = current_user.get("role")
        user_id = current_user.get("sub")

        if user_role != required_role and user_role != "admin":
            # Log authorization failure
            ip_address = request.client.host if request and request.client else None
            user_agent = request.headers.get("user-agent") if request else None

            await log_authorization_failure(
                user_id=str(user_id) if user_id else None,
                required_permission=f"role:{required_role}",
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )

        return current_user

    return role_checker


async def require_admin(
    current_user: dict = Depends(get_current_user),
    request: Request = None,
) -> dict:
    """
    Require admin role for access.

    Args:
        current_user: Current user from token
        request: FastAPI request

    Returns:
        Current user

    Raises:
        HTTPException: If user is not admin
    """
    if current_user.get("role") != "admin":
        user_id = current_user.get("sub")
        user_role = current_user.get("role")

        # Log authorization failure
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        await log_authorization_failure(
            user_id=str(user_id) if user_id else None,
            required_permission="role:admin",
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
