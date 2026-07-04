"""Audit log retention service for compliance."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuditRetentionService:
    """Service for managing audit log retention."""

    def __init__(self, db: AsyncSession):
        """
        Initialize audit retention service.

        Args:
            db: Database session
        """
        self.db = db
        self.logger = logger

    async def delete_old_logs(self, retention_days: Optional[int] = None) -> int:
        """
        Delete audit logs older than retention period.

        Args:
            retention_days: Retention period in days (default: from config, minimum 365)

        Returns:
            Number of logs deleted
        """
        try:
            # Use configured retention or default to 1 year (365 days)
            if retention_days is None:
                retention_days = settings.audit_log_retention_days if hasattr(settings, 'audit_log_retention_days') else 365

            # Ensure minimum retention of 1 year
            retention_days = max(retention_days, 365)

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Count logs to be deleted
            count_query = select(AuditLog).where(AuditLog.timestamp < cutoff_date)
            count_result = await self.db.execute(count_query)
            logs_to_delete = len(count_result.scalars().all())

            # Delete old logs
            delete_query = delete(AuditLog).where(AuditLog.timestamp < cutoff_date)
            result = await self.db.execute(delete_query)
            await self.db.commit()

            deleted_count = result.rowcount

            self.logger.info(
                f"Deleted {deleted_count} audit logs older than {retention_days} days "
                f"(cutoff: {cutoff_date})"
            )

            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to delete old audit logs: {e}")
            await self.db.rollback()
            return 0

    async def get_log_count(self) -> int:
        """
        Get total count of audit logs.

        Returns:
            Total number of audit logs
        """
        try:
            query = select(AuditLog)
            result = await self.db.execute(query)
            return len(result.scalars().all())
        except Exception as e:
            self.logger.error(f"Failed to get log count: {e}")
            return 0

    async def get_log_count_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """
        Get count of audit logs within a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Number of logs in date range
        """
        try:
            query = select(AuditLog).where(
                AuditLog.timestamp >= start_date,
                AuditLog.timestamp <= end_date,
            )
            result = await self.db.execute(query)
            return len(result.scalars().all())
        except Exception as e:
            self.logger.error(f"Failed to get log count by date range: {e}")
            return 0

    async def get_retention_status(self) -> dict:
        """
        Get retention status and statistics.

        Returns:
            Dictionary with retention status
        """
        try:
            retention_days = settings.audit_log_retention_days if hasattr(settings, 'audit_log_retention_days') else 365
            retention_days = max(retention_days, 365)

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Get total count
            total_count = await self.get_log_count()

            # Get count of logs to be deleted
            count_query = select(AuditLog).where(AuditLog.timestamp < cutoff_date)
            count_result = await self.db.execute(count_query)
            old_count = len(count_result.scalars().all())

            # Get count of recent logs
            recent_count = total_count - old_count

            return {
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "total_logs": total_count,
                "logs_to_delete": old_count,
                "recent_logs": recent_count,
            }

        except Exception as e:
            self.logger.error(f"Failed to get retention status: {e}")
            return {
                "error": str(e),
            }
