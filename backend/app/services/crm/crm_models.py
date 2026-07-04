"""CRM data models for Contact, Account, Purchase, and Support Ticket."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CRMType(str, Enum):
    """Supported CRM systems."""

    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    ZOHO = "zoho"
    FRESHWORKS = "freshworks"


class ContactStatus(str, Enum):
    """Contact status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BLOCKED = "blocked"


class AccountType(str, Enum):
    """Account type."""

    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class PurchaseStatus(str, Enum):
    """Purchase status."""

    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TicketStatus(str, Enum):
    """Support ticket status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CRMContact(BaseModel):
    """CRM Contact model."""

    contact_id: str = Field(description="Unique contact ID in CRM")
    first_name: str = Field(description="First name")
    last_name: str = Field(description="Last name")
    email: str = Field(description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    status: ContactStatus = Field(default=ContactStatus.ACTIVE, description="Contact status")
    account_id: Optional[str] = Field(default=None, description="Associated account ID")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom CRM fields")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class CRMAccount(BaseModel):
    """CRM Account model."""

    account_id: str = Field(description="Unique account ID in CRM")
    account_name: str = Field(description="Account name")
    account_type: AccountType = Field(default=AccountType.BUSINESS, description="Account type")
    industry: Optional[str] = Field(default=None, description="Industry")
    website: Optional[str] = Field(default=None, description="Website")
    employee_count: Optional[int] = Field(default=None, description="Number of employees")
    annual_revenue: Optional[float] = Field(default=None, description="Annual revenue")
    billing_address: Optional[dict[str, str]] = Field(default=None, description="Billing address")
    shipping_address: Optional[dict[str, str]] = Field(default=None, description="Shipping address")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom CRM fields")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class CRMPurchase(BaseModel):
    """CRM Purchase model."""

    purchase_id: str = Field(description="Unique purchase ID in CRM")
    contact_id: str = Field(description="Contact ID")
    account_id: Optional[str] = Field(default=None, description="Account ID")
    product_name: str = Field(description="Product name")
    product_id: Optional[str] = Field(default=None, description="Product ID")
    quantity: int = Field(default=1, description="Quantity purchased")
    unit_price: float = Field(description="Unit price")
    total_amount: float = Field(description="Total amount")
    currency: str = Field(default="USD", description="Currency code")
    status: PurchaseStatus = Field(default=PurchaseStatus.COMPLETED, description="Purchase status")
    purchase_date: datetime = Field(description="Purchase date")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom CRM fields")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class CRMSupportTicket(BaseModel):
    """CRM Support Ticket model."""

    ticket_id: str = Field(description="Unique ticket ID in CRM")
    contact_id: str = Field(description="Contact ID")
    account_id: Optional[str] = Field(default=None, description="Account ID")
    subject: str = Field(description="Ticket subject")
    description: str = Field(description="Ticket description")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Ticket status")
    priority: str = Field(default="medium", description="Ticket priority")
    category: Optional[str] = Field(default=None, description="Ticket category")
    assigned_to: Optional[str] = Field(default=None, description="Assigned agent ID")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    resolved_at: Optional[datetime] = Field(default=None, description="Resolution timestamp")
    custom_fields: dict[str, Any] = Field(default_factory=dict, description="Custom CRM fields")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class CRMWebhookEvent(BaseModel):
    """CRM webhook event model."""

    event_id: str = Field(description="Unique event ID")
    event_type: str = Field(description="Event type (contact.created, account.updated, etc.)")
    crm_type: CRMType = Field(description="CRM system type")
    object_type: str = Field(description="Object type (contact, account, purchase, ticket)")
    object_id: str = Field(description="Object ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Event timestamp")
    data: dict[str, Any] = Field(description="Event data payload")
    processed: bool = Field(default=False, description="Whether event has been processed")
    processed_at: Optional[datetime] = Field(default=None, description="Processing timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if processing failed")
