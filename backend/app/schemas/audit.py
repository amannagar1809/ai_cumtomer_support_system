"""Audit log schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Response for audit log entry."""

    id: UUID = Field(..., description="Log entry ID")
    user_id: Optional[UUID] = Field(default=None, description="User ID")
    user_email: Optional[str] = Field(default=None, description="User email")
    user_role: Optional[str] = Field(default=None, description="User role")
    action: str = Field(..., description="Action performed")
    resource_type: Optional[str] = Field(default=None, description="Resource type")
    resource_id: Optional[str] = Field(default=None, description="Resource ID")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    old_values: Optional[dict] = Field(default=None, description="Old values")
    new_values: Optional[dict] = Field(default=None, description="New values")
    success: str = Field(..., description="Success status")
    failure_reason: Optional[str] = Field(default=None, description="Failure reason")
    timestamp: datetime = Field(..., description="Timestamp")


class AuditLogExportRequest(BaseModel):
    """Request for audit log export."""

    start_date: Optional[datetime] = Field(default=None, description="Start date for export")
    end_date: Optional[datetime] = Field(default=None, description="End date for export")
    user_id: Optional[UUID] = Field(default=None, description="Filter by user ID")
    action: Optional[str] = Field(default=None, description="Filter by action")
    resource_type: Optional[str] = Field(default=None, description="Filter by resource type")
    format: str = Field(default="json", description="Export format (json, csv)")


class AuditLogExportResponse(BaseModel):
    """Response for audit log export."""

    total_logs: int = Field(..., description="Total number of logs exported")
    format: str = Field(..., description="Export format")
    data: list[AuditLogResponse] = Field(..., description="Exported audit logs")
    export_timestamp: datetime = Field(..., description="Export timestamp")


class ChainIntegrityResponse(BaseModel):
    """Response for chain integrity verification."""

    verified: bool = Field(..., description="Whether chain is verified")
    total_logs: int = Field(..., description="Total number of logs")
    verified_count: int = Field(..., description="Number of verified logs")
    tampered_count: int = Field(..., description="Number of tampered logs")
    message: str = Field(..., description="Verification message")


class RetentionStatusResponse(BaseModel):
    """Response for retention status."""

    retention_days: int = Field(..., description="Retention period in days")
    cutoff_date: str = Field(..., description="Cutoff date for old logs")
    total_logs: int = Field(..., description="Total number of logs")
    logs_to_delete: int = Field(..., description="Number of logs to delete")
    recent_logs: int = Field(..., description="Number of recent logs")
