import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomerType(str, enum.Enum):
    regular = "regular"
    premium = "premium"
    vip = "vip"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="ck_users_email_format",
        ),
        CheckConstraint(
            "phone IS NULL OR phone ~ '^\\+[1-9][0-9]{1,14}$'",
            name="ck_users_phone_e164",
        ),
        Index("ix_users_email", "email"),
        Index("ix_users_phone", "phone"),
        Index("ix_users_customer_type", "customer_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="en"
    )
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(
            CustomerType,
            name="customer_type",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        server_default=CustomerType.regular.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
