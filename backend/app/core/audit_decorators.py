"""Audit log decorators for endpoint logging."""

import functools
import logging
from typing import Callable, Optional

from fastapi import Request

from app.services.audit.audit_service import AuditService

logger = logging.getLogger(__name__)


def audit_log(action: str, resource_type: Optional[str] = None):
    """
    Decorator to audit log endpoint calls.

    Args:
        action: Action being performed
        resource_type: Type of resource being accessed/modified

    Returns:
        Decorator function
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from kwargs
            request = kwargs.get("request")
            db = kwargs.get("db")

            # Get user info if available
            current_user = kwargs.get("current_user")
            user_id = None
            user_email = None
            user_role = None

            if current_user:
                from uuid import UUID
                user_id = UUID(current_user.get("sub")) if current_user.get("sub") else None
                user_email = current_user.get("email")
                user_role = current_user.get("role")

            # Get request info
            ip_address = request.client.host if request and request.client else None
            user_agent = request.headers.get("user-agent") if request else None

            # Get resource ID from path parameters
            resource_id = None
            if request:
                path_params = request.path_params
                if "id" in path_params:
                    resource_id = str(path_params["id"])
                elif "user_id" in path_params:
                    resource_id = str(path_params["user_id"])
                elif "conversation_id" in path_params:
                    resource_id = str(path_params["conversation_id"])

            # Initialize audit service if db is available
            audit_service = None
            if db:
                audit_service = AuditService(db)

            # Log the event
            if audit_service:
                try:
                    await audit_service.log_event(
                        action=action,
                        user_id=user_id,
                        user_email=user_email,
                        user_role=user_role,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")

            # Execute the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def audit_data_access(resource_type: str):
    """
    Decorator to audit data access.

    Args:
        resource_type: Type of resource being accessed

    Returns:
        Decorator function
    """
    return audit_log("data_access", resource_type)


def audit_data_modification(resource_type: str):
    """
    Decorator to audit data modification.

    Args:
        resource_type: Type of resource being modified

    Returns:
        Decorator function
    """
    return audit_log("data_modification", resource_type)


def audit_role_change():
    """
    Decorator to audit role changes.

    Returns:
        Decorator function
    """
    return audit_log("role_change", "user")
