"""Permission model for role-based access control."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class Permission(Base):
    """Permission model for RBAC."""

    __tablename__ = "permissions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    resource = Column(String(50), nullable=False, index=True)  # conversations, users, analytics, billing, etc.
    action = Column(String(50), nullable=False)  # create, read, update, delete, manage
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name}, resource={self.resource}, action={self.action})>"
