"""Audit log API endpoints for compliance."""

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin, require_permission
from app.core.database import get_db
from app.schemas.audit import (
    AuditLogExportRequest,
    AuditLogExportResponse,
    AuditLogResponse,
    ChainIntegrityResponse,
    RetentionStatusResponse,
)
from app.services.audit.audit_retention import AuditRetentionService
from app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/logs",
    response_model=list[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get audit logs"
)
async def get_audit_logs(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(require_permission("analytics.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """
    Get audit logs with optional filters.

    This endpoint requires analytics.read permission.

    Args:
        start_date: Start date filter
        end_date: End date filter
        user_id: Filter by user ID
        action: Filter by action
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        limit: Maximum number of logs
        offset: Offset for pagination
        current_user: Current user from JWT
        db: Database session

    Returns:
        List of audit logs
    """
    audit_service = AuditService(db)

    if start_date and end_date:
        logs = await audit_service.get_logs_by_date_range(start_date, end_date, limit, offset)
    elif user_id:
        logs = await audit_service.get_logs_by_user(user_id, limit, offset)
    elif action:
        logs = await audit_service.get_logs_by_action(action, limit, offset)
    elif resource_type and resource_id:
        logs = await audit_service.get_logs_by_resource(resource_type, resource_id, limit, offset)
    else:
        # Get all logs with date range defaulting to last 30 days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        logs = await audit_service.get_logs_by_date_range(start_date, end_date, limit, offset)

    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_email=log.user_email,
            user_role=log.user_role,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            old_values=json.loads(log.old_values) if log.old_values else None,
            new_values=json.loads(log.new_values) if log.new_values else None,
            success=log.success,
            failure_reason=log.failure_reason,
            timestamp=log.timestamp,
        )
        for log in logs
    ]


@router.post(
    "/export",
    response_model=AuditLogExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export audit logs for compliance"
)
async def export_audit_logs(
    body: AuditLogExportRequest,
    current_user: dict = Depends(require_permission("analytics.read")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogExportResponse:
    """
    Export audit logs for compliance reviews.

    This endpoint requires analytics.read permission.

    Args:
        body: Export request with filters and format
        current_user: Current user from JWT
        db: Database session

    Returns:
        Exported audit logs
    """
    audit_service = AuditService(db)

    # Get logs based on filters
    if body.start_date and body.end_date:
        logs = await audit_service.get_logs_by_date_range(
            body.start_date,
            body.end_date,
            limit=10000,
            offset=0,
        )
    elif body.user_id:
        logs = await audit_service.get_logs_by_user(body.user_id, limit=10000, offset=0)
    elif body.action:
        logs = await audit_service.get_logs_by_action(body.action, limit=10000, offset=0)
    elif body.resource_type:
        logs = await audit_service.get_logs_by_resource(
            body.resource_type,
            body.resource_id or "",
            limit=10000,
            offset=0,
        )
    else:
        # Default to last 90 days
        start_date = datetime.utcnow() - timedelta(days=90)
        end_date = datetime.utcnow()
        logs = await audit_service.get_logs_by_date_range(start_date, end_date, limit=10000, offset=0)

    # Convert to response format
    log_responses = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_email=log.user_email,
            user_role=log.user_role,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            old_values=json.loads(log.old_values) if log.old_values else None,
            new_values=json.loads(log.new_values) if log.new_values else None,
            success=log.success,
            failure_reason=log.failure_reason,
            timestamp=log.timestamp,
        )
        for log in logs
    ]

    return AuditLogExportResponse(
        total_logs=len(log_responses),
        format=body.format,
        data=log_responses,
        export_timestamp=datetime.utcnow(),
    )


@router.get(
    "/export/csv",
    status_code=status.HTTP_200_OK,
    summary="Export audit logs as CSV"
)
async def export_audit_logs_csv(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    current_user: dict = Depends(require_permission("analytics.read")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export audit logs as CSV for compliance reviews.

    This endpoint requires analytics.read permission.

    Args:
        start_date: Start date filter
        end_date: End date filter
        user_id: Filter by user ID
        action: Filter by action
        resource_type: Filter by resource type
        current_user: Current user from JWT
        db: Database session

    Returns:
        CSV file with audit logs
    """
    audit_service = AuditService(db)

    # Get logs based on filters
    if start_date and end_date:
        logs = await audit_service.get_logs_by_date_range(start_date, end_date, limit=10000, offset=0)
    elif user_id:
        logs = await audit_service.get_logs_by_user(user_id, limit=10000, offset=0)
    elif action:
        logs = await audit_service.get_logs_by_action(action, limit=10000, offset=0)
    elif resource_type:
        logs = await audit_service.get_logs_by_resource(resource_type, "", limit=10000, offset=0)
    else:
        # Default to last 90 days
        start_date = datetime.utcnow() - timedelta(days=90)
        end_date = datetime.utcnow()
        logs = await audit_service.get_logs_by_date_range(start_date, end_date, limit=10000, offset=0)

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "id", "user_id", "user_email", "user_role", "action",
        "resource_type", "resource_id", "ip_address", "user_agent",
        "old_values", "new_values", "success", "failure_reason", "timestamp",
    ])

    # Write rows
    for log in logs:
        writer.writerow([
            str(log.id),
            str(log.user_id) if log.user_id else "",
            log.user_email or "",
            log.user_role or "",
            log.action,
            log.resource_type or "",
            log.resource_id or "",
            log.ip_address or "",
            log.user_agent or "",
            log.old_values or "",
            log.new_values or "",
            log.success,
            log.failure_reason or "",
            log.timestamp.isoformat(),
        ])

    # Create response
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit_logs.csv",
        },
    )


@router.get(
    "/integrity",
    response_model=ChainIntegrityResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify audit log chain integrity"
)
async def verify_chain_integrity(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ChainIntegrityResponse:
    """
    Verify audit log chain integrity for tamper detection.

    This endpoint requires admin permission.

    Args:
        current_user: Current user from JWT
        db: Database session

    Returns:
        Chain integrity verification results
    """
    audit_service = AuditService(db)
    verification_result = await audit_service.verify_chain_integrity()

    return ChainIntegrityResponse(
        verified=verification_result.get("verified", False),
        total_logs=verification_result.get("total_logs", 0),
        verified_count=verification_result.get("verified_count", 0),
        tampered_count=verification_result.get("tampered_count", 0),
        message=verification_result.get("message", ""),
    )


@router.get(
    "/retention",
    response_model=RetentionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audit log retention status"
)
async def get_retention_status(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> RetentionStatusResponse:
    """
    Get audit log retention status and statistics.

    This endpoint requires admin permission.

    Args:
        current_user: Current user from JWT
        db: Database session

    Returns:
        Retention status
    """
    retention_service = AuditRetentionService(db)
    status = await retention_service.get_retention_status()

    return RetentionStatusResponse(
        retention_days=status.get("retention_days", 365),
        cutoff_date=status.get("cutoff_date", ""),
        total_logs=status.get("total_logs", 0),
        logs_to_delete=status.get("logs_to_delete", 0),
        recent_logs=status.get("recent_logs", 0),
    )


@router.delete(
    "/retention/cleanup",
    status_code=status.HTTP_200_OK,
    summary="Delete old audit logs"
)
async def cleanup_old_logs(
    retention_days: Optional[int] = Query(None, ge=365, description="Retention period in days"),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete audit logs older than retention period.

    This endpoint requires admin permission.

    Args:
        retention_days: Retention period in days (minimum 365)
        current_user: Current user from JWT
        db: Database session

    Returns:
        Deletion results
    """
    retention_service = AuditRetentionService(db)
    deleted_count = await retention_service.delete_old_logs(retention_days)

    return {
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} old audit logs",
    }
