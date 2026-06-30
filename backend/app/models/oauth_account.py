"""OAuth account model for linking external OAuth providers to internal users."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class OAuthAccount(Base):
    """OAuth account model for linking external providers."""

    __tablename__ = "oauth_accounts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Provider information
    provider = Column(String(50), nullable=False)  # google, microsoft, github, slack
    provider_user_id = Column(String(255), nullable=False)  # External user ID from provider
    
    # OAuth tokens
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # User info from provider
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Metadata
    raw_user_data = Column(String(5000), nullable=True)  # JSON string of raw user data
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: provider + provider_user_id must be unique
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
    )

    def __repr__(self):
        return f"<OAuthAccount(id={self.id}, provider={self.provider}, provider_user_id={self.provider_user_id}, user_id={self.user_id})>"
