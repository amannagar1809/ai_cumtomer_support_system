"""Role-based access control (RBAC) configuration and utilities."""

import logging
from typing import Optional

from app.core.database import Base

logger = logging.getLogger(__name__)


# Role definitions
ROLES = {
    "admin": "Admin - Full system access, user management, billing",
    "support_agent": "Support Agent - View conversations, create tickets, reply to escalated",
    "supervisor": "Supervisor - Agent management, analytics, quality review",
    "viewer": "Viewer - Read-only analytics only",
}


# Role-permission matrix
ROLE_PERMISSIONS = {
    "admin": [
        # Users
        "users.create",
        "users.read",
        "users.update",
        "users.delete",
        "users.manage",
        # Conversations
        "conversations.create",
        "conversations.read",
        "conversations.update",
        "conversations.delete",
        "conversations.manage",
        # Analytics
        "analytics.read",
        "analytics.manage",
        # Billing
        "billing.read",
        "billing.manage",
        # Knowledge Base
        "knowledge_base.create",
        "knowledge_base.read",
        "knowledge_base.update",
        "knowledge_base.delete",
        "knowledge_base.manage",
        # Settings
        "settings.read",
        "settings.update",
        "settings.manage",
    ],
    "support_agent": [
        # Conversations
        "conversations.read",
        "conversations.update",  # Reply to conversations
        # Tickets
        "tickets.create",
        "tickets.read",
        "tickets.update",
        # Knowledge Base (read only)
        "knowledge_base.read",
    ],
    "supervisor": [
        # Users (view and manage agents)
        "users.read",
        "users.manage",
        # Conversations
        "conversations.read",
        "conversations.update",
        # Analytics
        "analytics.read",
        "analytics.manage",
        # Quality Review
        "quality_review.read",
        "quality_review.create",
        "quality_review.update",
        # Knowledge Base
        "knowledge_base.read",
        "knowledge_base.update",
        # Tickets
        "tickets.read",
        "tickets.update",
    ],
    "viewer": [
        # Analytics (read only)
        "analytics.read",
        # Conversations (read only)
        "conversations.read",
    ],
}


# Permission definitions
PERMISSIONS = {
    # User permissions
    "users.create": "Create new users",
    "users.read": "View user information",
    "users.update": "Update user information",
    "users.delete": "Delete users",
    "users.manage": "Full user management",
    
    # Conversation permissions
    "conversations.create": "Create new conversations",
    "conversations.read": "View conversations",
    "conversations.update": "Update conversations (reply)",
    "conversations.delete": "Delete conversations",
    "conversations.manage": "Full conversation management",
    
    # Ticket permissions
    "tickets.create": "Create tickets",
    "tickets.read": "View tickets",
    "tickets.update": "Update tickets",
    "tickets.delete": "Delete tickets",
    "tickets.manage": "Full ticket management",
    
    # Analytics permissions
    "analytics.read": "View analytics",
    "analytics.manage": "Manage analytics settings",
    
    # Billing permissions
    "billing.read": "View billing information",
    "billing.manage": "Manage billing",
    
    # Knowledge Base permissions
    "knowledge_base.create": "Create knowledge base articles",
    "knowledge_base.read": "View knowledge base articles",
    "knowledge_base.update": "Update knowledge base articles",
    "knowledge_base.delete": "Delete knowledge base articles",
    "knowledge_base.manage": "Full knowledge base management",
    
    # Quality Review permissions
    "quality_review.read": "View quality reviews",
    "quality_review.create": "Create quality reviews",
    "quality_review.update": "Update quality reviews",
    "quality_review.delete": "Delete quality reviews",
    "quality_review.manage": "Full quality review management",
    
    # Settings permissions
    "settings.read": "View system settings",
    "settings.update": "Update system settings",
    "settings.manage": "Full settings management",
}


def has_permission(user_role: str, required_permission: str) -> bool:
    """
    Check if user role has the required permission.

    Args:
        user_role: User's role
        required_permission: Permission to check

    Returns:
        True if user has permission, False otherwise
    """
    # Admin has all permissions
    if user_role == "admin":
        return True

    # Get permissions for user's role
    role_perms = ROLE_PERMISSIONS.get(user_role, [])

    # Check if required permission is in role's permissions
    return required_permission in role_perms


def has_any_permission(user_role: str, required_permissions: list[str]) -> bool:
    """
    Check if user role has any of the required permissions.

    Args:
        user_role: User's role
        required_permissions: List of permissions to check

    Returns:
        True if user has any of the permissions, False otherwise
    """
    # Admin has all permissions
    if user_role == "admin":
        return True

    # Get permissions for user's role
    role_perms = ROLE_PERMISSIONS.get(user_role, [])

    # Check if any required permission is in role's permissions
    return any(perm in role_perms for perm in required_permissions)


def has_all_permissions(user_role: str, required_permissions: list[str]) -> bool:
    """
    Check if user role has all of the required permissions.

    Args:
        user_role: User's role
        required_permissions: List of permissions to check

    Returns:
        True if user has all permissions, False otherwise
    """
    # Admin has all permissions
    if user_role == "admin":
        return True

    # Get permissions for user's role
    role_perms = ROLE_PERMISSIONS.get(user_role, [])

    # Check if all required permissions are in role's permissions
    return all(perm in role_perms for perm in required_permissions)


def get_role_permissions(role: str) -> list[str]:
    """
    Get all permissions for a role.

    Args:
        role: Role name

    Returns:
        List of permissions for the role
    """
    return ROLE_PERMISSIONS.get(role, [])


def is_valid_role(role: str) -> bool:
    """
    Check if role is valid.

    Args:
        role: Role name

    Returns:
        True if role is valid, False otherwise
    """
    return role in ROLES


def get_all_roles() -> dict[str, str]:
    """
    Get all available roles.

    Returns:
        Dictionary of role names and descriptions
    """
    return ROLES.copy()
