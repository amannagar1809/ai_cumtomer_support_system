"""Role model for role-based access control."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.core.database import Base

# Many-to-many relationship table for roles and permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", PG_UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", PG_UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True),
)


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)  # admin, support_agent, supervisor, viewer
    description = Column(String(255), nullable=True)
    
    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, backref="roles")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"
