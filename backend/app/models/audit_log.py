"""Audit log model for compliance tracking."""

import hashlib
import json
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class AuditLog(Base):
    """Audit log model for tracking sensitive actions."""

    __tablename__ = "audit_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    
    # User information
    user_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    user_role = Column(String(50), nullable=True)
    
    # Action information
    action = Column(String(100), nullable=False, index=True)  # login, data_access, data_modification, role_change, etc.
    resource_type = Column(String(50), nullable=True, index=True)  # user, conversation, ticket, etc.
    resource_id = Column(String(255), nullable=True, index=True)  # ID of the affected resource
    
    # Request information
    ip_address = Column(String(45), nullable=True, index=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    
    # Change details
    old_values = Column(Text, nullable=True)  # JSON string of old values
    new_values = Column(Text, nullable=True)  # JSON string of new values
    
    # Metadata
    success = Column(String(10), nullable=False, default="success")  # success, failure
    failure_reason = Column(String(255), nullable=True)
    
    # Tamper detection
    previous_log_hash = Column(String(64), nullable=True, index=True)  # Hash of previous log entry
    current_log_hash = Column(String(64), nullable=False, index=True)  # Hash of current log entry
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id}, timestamp={self.timestamp})>"

    def compute_hash(self) -> str:
        """
        Compute hash for tamper detection.

        Returns:
            SHA-256 hash of the log entry
        """
        # Create hashable string from log data
        hash_data = {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "success": self.success,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "previous_log_hash": self.previous_log_hash,
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
