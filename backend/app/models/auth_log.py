"""Authentication log model for tracking authentication attempts."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class AuthLog(Base):
    """Authentication log model."""

    __tablename__ = "auth_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)  # Nullable for failed login attempts
    email = Column(String(255), nullable=True)
    
    # Authentication details
    auth_type = Column(String(50), nullable=False)  # login, logout, refresh, token_validation
    success = Column(String(10), nullable=False)  # success, failure
    failure_reason = Column(String(255), nullable=True)  # invalid_credentials, expired_token, etc.
    
    # Request details
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    
    # Token details
    token_type = Column(String(20), nullable=True)  # access, refresh
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuthLog(id={self.id}, user_id={self.user_id}, auth_type={self.auth_type}, success={self.success})>"
