"""Audit logging service for compliance tracking."""

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for audit logging operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize audit service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def _get_previous_log_hash(self) -> Optional[str]:
        """
        Get hash of the most recent log entry for chain verification.

        Returns:
            Hash of previous log entry or None if no logs exist
        """
        try:
            query = (
                select(AuditLog.current_log_hash)
                .order_by(AuditLog.timestamp.desc())
                .limit(1)
            )
            result = await self.db.execute(query)
            previous_hash = result.scalar_one_or_none()
            return previous_hash
        except Exception as e:
            self.logger.error(f"Failed to get previous log hash: {e}")
            return None

    async def log_event(
        self,
        action: str,
        user_id: Optional[UUID] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log an audit event.

        Args:
            action: Action performed (login, data_access, data_modification, role_change, etc.)
            user_id: User ID
            user_email: User email
            user_role: User role
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            ip_address: IP address of the request
            user_agent: User agent string
            old_values: Old values before change (JSON serializable)
            new_values: New values after change (JSON serializable)
            success: Whether the action was successful
            failure_reason: Reason for failure if unsuccessful

        Returns:
            Audit log entry or None if logging failed
        """
        try:
            # Get previous log hash for chain verification
            previous_hash = await self._get_previous_log_hash()

            # Create audit log entry
            audit_log = AuditLog(
                user_id=user_id,
                user_email=user_email,
                user_role=user_role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None,
                success="success" if success else "failure",
                failure_reason=failure_reason,
                previous_log_hash=previous_hash,
                timestamp=datetime.utcnow(),
            )

            # Compute hash for tamper detection
            audit_log.current_log_hash = audit_log.compute_hash()

            # Save to database
            self.db.add(audit_log)
            await self.db.commit()

            self.logger.info(
                f"Audit log created: action={action}, user_id={user_id}, "
                f"resource_type={resource_type}, resource_id={resource_id}"
            )

            return audit_log

        except Exception as e:
            self.logger.error(f"Failed to create audit log: {e}")
            await self.db.rollback()
            return None

    async def log_login(
        self,
        user_id: UUID,
        user_email: str,
        user_role: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log login event.

        Args:
            user_id: User ID
            user_email: User email
            user_role: User role
            ip_address: IP address
            user_agent: User agent
            success: Whether login was successful
            failure_reason: Reason for failure

        Returns:
            Audit log entry
        """
        return await self.log_event(
            action="login",
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )

    async def log_data_access(
        self,
        user_id: UUID,
        user_email: str,
        user_role: str,
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log data access event.

        Args:
            user_id: User ID
            user_email: User email
            user_role: User role
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            ip_address: IP address
            user_agent: User agent

        Returns:
            Audit log entry
        """
        return await self.log_event(
            action="data_access",
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_data_modification(
        self,
        user_id: UUID,
        user_email: str,
        user_role: str,
        resource_type: str,
        resource_id: str,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log data modification event.

        Args:
            user_id: User ID
            user_email: User email
            user_role: User role
            resource_type: Type of resource modified
            resource_id: ID of resource modified
            old_values: Old values before modification
            new_values: New values after modification
            ip_address: IP address
            user_agent: User agent

        Returns:
            Audit log entry
        """
        return await self.log_event(
            action="data_modification",
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_role_change(
        self,
        user_id: UUID,
        user_email: str,
        user_role: str,
        target_user_id: UUID,
        old_role: str,
        new_role: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Log role change event.

        Args:
            user_id: User ID of the person making the change
            user_email: Email of the person making the change
            user_role: Role of the person making the change
            target_user_id: User ID of the person whose role was changed
            old_role: Old role
            new_role: New role
            ip_address: IP address
            user_agent: User agent

        Returns:
            Audit log entry
        """
        return await self.log_event(
            action="role_change",
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            resource_type="user",
            resource_id=str(target_user_id),
            old_values={"role": old_role},
            new_values={"role": new_role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def verify_chain_integrity(self) -> dict:
        """
        Verify audit log chain integrity for tamper detection.

        Returns:
            Dictionary with verification results
        """
        try:
            query = select(AuditLog).order_by(AuditLog.timestamp.asc())
            result = await self.db.execute(query)
            logs = result.scalars().all()

            if not logs:
                return {"verified": True, "message": "No logs to verify", "count": 0}

            previous_hash = None
            tampered_count = 0
            verified_count = 0

            for log in logs:
                # Recompute hash
                computed_hash = log.compute_hash()

                # Check if hash matches
                if computed_hash != log.current_log_hash:
                    tampered_count += 1
                    self.logger.warning(f"Tampered log detected: id={log.id}")
                else:
                    verified_count += 1

                # Check chain integrity
                if previous_hash and log.previous_log_hash != previous_hash:
                    tampered_count += 1
                    self.logger.warning(f"Chain break detected: id={log.id}")

                previous_hash = log.current_log_hash

            return {
                "verified": tampered_count == 0,
                "total_logs": len(logs),
                "verified_count": verified_count,
                "tampered_count": tampered_count,
                "message": f"Chain integrity: {tampered_count} tampered logs detected",
            }

        except Exception as e:
            self.logger.error(f"Failed to verify chain integrity: {e}")
            return {
                "verified": False,
                "error": str(e),
                "message": "Failed to verify chain integrity",
            }

    async def get_logs_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of audit logs
        """
        try:
            query = (
                select(AuditLog)
                .where(AuditLog.user_id == user_id)
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Failed to get logs by user: {e}")
            return []

    async def get_logs_by_action(
        self,
        action: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs by action type.

        Args:
            action: Action type
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of audit logs
        """
        try:
            query = (
                select(AuditLog)
                .where(AuditLog.action == action)
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Failed to get logs by action: {e}")
            return []

    async def get_logs_by_resource(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific resource.

        Args:
            resource_type: Type of resource
            resource_id: ID of resource
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of audit logs
        """
        try:
            query = (
                select(AuditLog)
                .where(
                    AuditLog.resource_type == resource_type,
                    AuditLog.resource_id == resource_id,
                )
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Failed to get logs by resource: {e}")
            return []

    async def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs within a date range.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            List of audit logs
        """
        try:
            query = (
                select(AuditLog)
                .where(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                )
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Failed to get logs by date range: {e}")
            return []
