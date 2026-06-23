"""Purchase history fetcher for fetching customer purchase data from CRM."""

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from app.core.redis import get_redis_client
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour TTL
CACHE_KEY_PREFIX = "purchase_history:"
HISTORY_DAYS = 90  # Last 90 days


class TransactionType(str, Enum):
    """Transaction type."""

    INVOICE = "invoice"
    PAYMENT = "payment"
    REFUND = "refund"
    CREDIT = "credit"


class TransactionStatus(str, Enum):
    """Transaction status."""

    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PurchaseType(str, Enum):
    """Purchase type."""

    SUBSCRIPTION = "subscription"
    ONE_TIME = "one_time"


class Transaction(BaseModel):
    """Transaction model."""

    transaction_id: str = Field(description="Unique transaction ID")
    date: datetime = Field(description="Transaction date")
    amount: float = Field(description="Transaction amount")
    currency: str = Field(default="USD", description="Currency code")
    status: TransactionStatus = Field(description="Transaction status")
    product: str = Field(description="Product name")
    product_id: Optional[str] = Field(default=None, description="Product ID")
    transaction_type: TransactionType = Field(description="Transaction type")
    purchase_type: PurchaseType = Field(description="Purchase type (subscription/one_time)")
    invoice_id: Optional[str] = Field(default=None, description="Invoice ID")
    payment_method: Optional[str] = Field(default=None, description="Payment method")
    failed_payment_flagged: bool = Field(default=False, description="Whether failed payment is flagged")
    raw_crm_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")


class PurchaseHistorySummary(BaseModel):
    """Purchase history summary."""

    customer_id: str = Field(description="Customer ID")
    total_transactions: int = Field(description="Total number of transactions")
    total_amount: float = Field(description="Total amount of all transactions")
    total_paid: float = Field(description="Total amount paid")
    total_refunded: float = Field(description="Total amount refunded")
    total_pending: float = Field(description="Total amount pending")
    total_failed: float = Field(description="Total amount failed")
    subscription_count: int = Field(description="Number of subscription purchases")
    one_time_count: int = Field(description="Number of one-time purchases")
    failed_payment_count: int = Field(description="Number of failed payments")
    customer_value: float = Field(description="Total customer value for prioritization")
    period_start: datetime = Field(description="Period start date")
    period_end: datetime = Field(description="Period end date")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update timestamp")


class PurchaseHistoryFetcher:
    """Purchase history fetcher for CRM data."""

    def __init__(self, cache_ttl_seconds: int = CACHE_TTL_SECONDS, history_days: int = HISTORY_DAYS):
        """
        Initialize purchase history fetcher.

        Args:
            cache_ttl_seconds: Cache TTL in seconds
            history_days: Number of days of history to fetch
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.history_days = history_days
        self.redis_client = None

    async def _get_redis_client(self):
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = get_redis_client()
        return self.redis_client

    def _generate_cache_key(self, customer_id: str) -> str:
        """
        Generate cache key for purchase history.

        Args:
            customer_id: Customer ID

        Returns:
            Cache key
        """
        return f"{CACHE_KEY_PREFIX}{customer_id}"

    async def _cache_purchase_history(self, customer_id: str, summary: PurchaseHistorySummary) -> None:
        """
        Cache purchase history in Redis.

        Args:
            customer_id: Customer ID
            summary: Purchase history summary
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            summary_json = summary.model_dump_json()
            await redis.setex(cache_key, self.cache_ttl_seconds, summary_json)
            logger.info(f"Cached purchase history for customer: {customer_id}")
        except Exception as e:
            logger.warning(f"Failed to cache purchase history: {e}")

    async def _get_cached_purchase_history(self, customer_id: str) -> Optional[PurchaseHistorySummary]:
        """
        Get cached purchase history from Redis.

        Args:
            customer_id: Customer ID

        Returns:
            Cached purchase history summary or None
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            summary_json = await redis.get(cache_key)

            if summary_json:
                summary_data = json.loads(summary_json)
                summary = PurchaseHistorySummary(**summary_data)
                logger.info(f"Retrieved cached purchase history for customer: {customer_id}")
                return summary

            return None
        except Exception as e:
            logger.warning(f"Failed to retrieve cached purchase history: {e}")
            return None

    async def _invalidate_cache(self, customer_id: str) -> None:
        """
        Invalidate cached purchase history.

        Args:
            customer_id: Customer ID
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(customer_id)
            await redis.delete(cache_key)
            logger.info(f"Invalidated purchase history cache for customer: {customer_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    def _map_crm_transaction(self, crm_data: dict[str, Any]) -> Transaction:
        """
        Map CRM transaction data to internal model.

        Args:
            crm_data: Raw CRM transaction data

        Returns:
            Transaction model
        """
        # Extract transaction fields
        transaction_id = crm_data.get("id", crm_data.get("transaction_id", "unknown"))
        date_str = crm_data.get("date", crm_data.get("created_at", ""))
        if date_str:
            try:
                if isinstance(date_str, str):
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    date = date_str
            except Exception:
                date = datetime.now(UTC)
        else:
            date = datetime.now(UTC)

        amount = float(crm_data.get("amount", crm_data.get("total", 0.0)))
        currency = crm_data.get("currency", "USD")
        status_str = crm_data.get("status", "completed").lower()
        status = TransactionStatus(status_str) if status_str in [e.value for e in TransactionStatus] else TransactionStatus.PENDING

        product = crm_data.get("product", crm_data.get("product_name", "Unknown"))
        product_id = crm_data.get("product_id", crm_data.get("sku", None))

        # Determine transaction type
        transaction_type_str = crm_data.get("type", crm_data.get("transaction_type", "payment")).lower()
        transaction_type = TransactionType(transaction_type_str) if transaction_type_str in [e.value for e in TransactionType] else TransactionType.PAYMENT

        # Determine purchase type (subscription vs one-time)
        purchase_type_str = crm_data.get("purchase_type", crm_data.get("billing_cycle", "one_time")).lower()
        if "subscription" in purchase_type_str or "recurring" in purchase_type_str:
            purchase_type = PurchaseType.SUBSCRIPTION
        else:
            purchase_type = PurchaseType.ONE_TIME

        invoice_id = crm_data.get("invoice_id", crm_data.get("invoice_number", None))
        payment_method = crm_data.get("payment_method", crm_data.get("payment_type", None))

        # Flag failed payments
        failed_payment_flagged = status == TransactionStatus.FAILED

        transaction = Transaction(
            transaction_id=transaction_id,
            date=date,
            amount=amount,
            currency=currency,
            status=status,
            product=product,
            product_id=product_id,
            transaction_type=transaction_type,
            purchase_type=purchase_type,
            invoice_id=invoice_id,
            payment_method=payment_method,
            failed_payment_flagged=failed_payment_flagged,
            raw_crm_data=crm_data,
        )

        return transaction

    def _calculate_summary(self, transactions: list[Transaction], customer_id: str) -> PurchaseHistorySummary:
        """
        Calculate purchase history summary.

        Args:
            transactions: List of transactions
            customer_id: Customer ID

        Returns:
            Purchase history summary
        """
        total_transactions = len(transactions)
        total_amount = sum(t.amount for t in transactions)
        total_paid = sum(t.amount for t in transactions if t.status == TransactionStatus.COMPLETED)
        total_refunded = sum(t.amount for t in transactions if t.status == TransactionStatus.REFUNDED or t.transaction_type == TransactionType.REFUND)
        total_pending = sum(t.amount for t in transactions if t.status == TransactionStatus.PENDING)
        total_failed = sum(t.amount for t in transactions if t.status == TransactionStatus.FAILED)

        subscription_count = sum(1 for t in transactions if t.purchase_type == PurchaseType.SUBSCRIPTION)
        one_time_count = sum(1 for t in transactions if t.purchase_type == PurchaseType.ONE_TIME)
        failed_payment_count = sum(1 for t in transactions if t.failed_payment_flagged)

        # Calculate customer value (total paid - total refunded)
        customer_value = total_paid - total_refunded

        # Determine period
        if transactions:
            dates = [t.date for t in transactions]
            period_start = min(dates)
            period_end = max(dates)
        else:
            period_start = datetime.now(UTC) - timedelta(days=self.history_days)
            period_end = datetime.now(UTC)

        summary = PurchaseHistorySummary(
            customer_id=customer_id,
            total_transactions=total_transactions,
            total_amount=total_amount,
            total_paid=total_paid,
            total_refunded=total_refunded,
            total_pending=total_pending,
            total_failed=total_failed,
            subscription_count=subscription_count,
            one_time_count=one_time_count,
            failed_payment_count=failed_payment_count,
            customer_value=customer_value,
            period_start=period_start,
            period_end=period_end,
        )

        return summary

    async def fetch_purchase_history(
        self,
        customer_id: str,
        crm_client: Optional[Any] = None,
    ) -> PurchaseHistorySummary:
        """
        Fetch purchase history for customer.

        Args:
            customer_id: Customer ID
            crm_client: CRM client (optional, for actual CRM query)

        Returns:
            Purchase history summary
        """
        # Check cache first
        cached_summary = await self._get_cached_purchase_history(customer_id)
        if cached_summary:
            return cached_summary

        # Fetch from CRM (placeholder - requires actual CRM client)
        if crm_client:
            # TODO: Implement actual CRM query for invoices, payments, refunds
            crm_transactions = []
            # crm_transactions = await crm_client.get_transactions(customer_id, days=self.history_days)
        else:
            # Placeholder data for testing
            crm_transactions = [
                {
                    "id": "txn_001",
                    "date": (datetime.now(UTC) - timedelta(days=10)).isoformat(),
                    "amount": 99.99,
                    "currency": "USD",
                    "status": "completed",
                    "product": "Premium Plan",
                    "product_id": "premium",
                    "type": "payment",
                    "purchase_type": "subscription",
                },
                {
                    "id": "txn_002",
                    "date": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
                    "amount": 49.99,
                    "currency": "USD",
                    "status": "completed",
                    "product": "Basic Plan",
                    "product_id": "basic",
                    "type": "payment",
                    "purchase_type": "subscription",
                },
            ]

        # Map CRM data to transactions
        transactions = [self._map_crm_transaction(t) for t in crm_transactions]

        # Calculate summary
        summary = self._calculate_summary(transactions, customer_id)

        # Cache the summary
        await self._cache_purchase_history(customer_id, summary)

        return summary

    async def invalidate_purchase_history_cache(self, customer_id: str) -> None:
        """
        Invalidate purchase history cache.

        Args:
            customer_id: Customer ID
        """
        await self._invalidate_cache(customer_id)
