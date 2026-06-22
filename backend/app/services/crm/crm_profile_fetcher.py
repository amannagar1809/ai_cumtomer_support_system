"""CRM profile fetcher for fetching customer profiles from CRM with caching."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from app.core.redis import get_redis_client
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour TTL
CACHE_KEY_PREFIX = "crm_profile:"


class CRMProfile(BaseModel):
    """CRM customer profile model."""

    customer_id: str = Field(description="Customer ID")
    customer_name: str = Field(description="Customer name")
    customer_tier: str = Field(default="regular", description="Customer tier (regular/premium/vip)")
    subscription_plan: Optional[str] = Field(default=None, description="Subscription plan")
    account_age_days: Optional[int] = Field(default=None, description="Account age in days")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    account_id: Optional[str] = Field(default=None, description="CRM account ID")
    contact_id: Optional[str] = Field(default=None, description="CRM contact ID")
    created_at: datetime = Field(description="Account creation date")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update timestamp")
    raw_crm_data: dict[str, Any] = Field(default_factory=dict, description="Raw CRM data")
    field_security: dict[str, bool] = Field(default_factory=dict, description="Field-level security flags")


class FieldSecurityConfig(BaseModel):
    """Field-level security configuration."""

    customer_name: bool = Field(default=True, description="Access to customer name")
    customer_tier: bool = Field(default=True, description="Access to customer tier")
    subscription_plan: bool = Field(default=True, description="Access to subscription plan")
    account_age: bool = Field(default=True, description="Access to account age")
    email: bool = Field(default=True, description="Access to email")
    phone: bool = Field(default=True, description="Access to phone number")


class CRMProfileFetcher:
    """CRM profile fetcher with caching and field-level security."""

    def __init__(
        self,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
        field_security: Optional[FieldSecurityConfig] = None,
    ):
        """
        Initialize CRM profile fetcher.

        Args:
            cache_ttl_seconds: Cache TTL in seconds
            field_security: Field-level security configuration
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.field_security = field_security or FieldSecurityConfig()
        self.redis_client = None

    async def _get_redis_client(self):
        """Get Redis client."""
        if self.redis_client is None:
            self.redis_client = get_redis_client()
        return self.redis_client

    def _generate_cache_key(self, identifier: str) -> str:
        """
        Generate cache key for profile.

        Args:
            identifier: Email or phone number

        Returns:
            Cache key
        """
        return f"{CACHE_KEY_PREFIX}{identifier}"

    async def _cache_profile(self, identifier: str, profile: CRMProfile) -> None:
        """
        Cache profile in Redis.

        Args:
            identifier: Email or phone number
            profile: CRM profile
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(identifier)
            profile_json = profile.model_dump_json()
            await redis.setex(cache_key, self.cache_ttl_seconds, profile_json)
            logger.info(f"Cached CRM profile for {identifier}")
        except Exception as e:
            logger.warning(f"Failed to cache CRM profile: {e}")

    async def _get_cached_profile(self, identifier: str) -> Optional[CRMProfile]:
        """
        Get cached profile from Redis.

        Args:
            identifier: Email or phone number

        Returns:
            Cached profile or None
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(identifier)
            profile_json = await redis.get(cache_key)

            if profile_json:
                profile_data = json.loads(profile_json)
                profile = CRMProfile(**profile_data)
                logger.info(f"Retrieved cached CRM profile for {identifier}")
                return profile

            return None
        except Exception as e:
            logger.warning(f"Failed to retrieve cached CRM profile: {e}")
            return None

    async def _invalidate_cache(self, identifier: str) -> None:
        """
        Invalidate cached profile.

        Args:
            identifier: Email or phone number
        """
        try:
            redis = await self._get_redis_client()
            cache_key = self._generate_cache_key(identifier)
            await redis.delete(cache_key)
            logger.info(f"Invalidated cache for {identifier}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    def _apply_field_security(self, profile: CRMProfile) -> CRMProfile:
        """
        Apply field-level security to profile.

        Args:
            profile: CRM profile

        Returns:
            Profile with secured fields
        """
        secured_profile = profile.model_copy()

        # Apply field-level security
        if not self.field_security.customer_name:
            secured_profile.customer_name = "REDACTED"
            secured_profile.field_security["customer_name"] = False

        if not self.field_security.customer_tier:
            secured_profile.customer_tier = "REDACTED"
            secured_profile.field_security["customer_tier"] = False

        if not self.field_security.subscription_plan:
            secured_profile.subscription_plan = "REDACTED"
            secured_profile.field_security["subscription_plan"] = False

        if not self.field_security.account_age:
            secured_profile.account_age_days = None
            secured_profile.field_security["account_age"] = False

        if not self.field_security.email:
            secured_profile.email = "REDACTED"
            secured_profile.field_security["email"] = False

        if not self.field_security.phone:
            secured_profile.phone = "REDACTED"
            secured_profile.field_security["phone"] = False

        return secured_profile

    def _map_crm_fields_to_profile(self, crm_data: dict[str, Any]) -> CRMProfile:
        """
        Map CRM fields to internal customer model.

        Args:
            crm_data: Raw CRM data

        Returns:
            CRM profile
        """
        # Extract fields from CRM data
        # This is a generic mapping - should be customized per CRM system
        customer_id = crm_data.get("id", crm_data.get("contact_id", "unknown"))
        customer_name = crm_data.get("name", crm_data.get("full_name", ""))
        if not customer_name:
            first_name = crm_data.get("first_name", "")
            last_name = crm_data.get("last_name", "")
            customer_name = f"{first_name} {last_name}".strip()

        customer_tier = crm_data.get("tier", crm_data.get("customer_type", "regular"))
        subscription_plan = crm_data.get("subscription_plan", crm_data.get("plan", None))

        # Calculate account age
        created_at_str = crm_data.get("created_at", crm_data.get("createddate", ""))
        if created_at_str:
            try:
                if isinstance(created_at_str, str):
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                else:
                    created_at = created_at_str
                account_age_days = (datetime.now(UTC) - created_at).days
            except Exception:
                account_age_days = None
        else:
            account_age_days = None

        email = crm_data.get("email", crm_data.get("emailaddress", None))
        phone = crm_data.get("phone", crm_data.get("mobilephone", None))
        account_id = crm_data.get("account_id", crm_data.get("accountid", None))
        contact_id = crm_data.get("contact_id", crm_data.get("contactid", None))

        profile = CRMProfile(
            customer_id=customer_id,
            customer_name=customer_name or "Unknown",
            customer_tier=customer_tier,
            subscription_plan=subscription_plan,
            account_age_days=account_age_days,
            email=email,
            phone=phone,
            account_id=account_id,
            contact_id=contact_id,
            created_at=created_at if created_at_str else datetime.now(UTC),
            raw_crm_data=crm_data,
        )

        return profile

    def _create_minimal_profile(self, identifier: str, identifier_type: str) -> CRMProfile:
        """
        Create minimal profile for missing customer.

        Args:
            identifier: Email or phone number
            identifier_type: Type of identifier (email/phone)

        Returns:
            Minimal CRM profile
        """
        if identifier_type == "email":
            customer_name = identifier.split("@")[0].replace(".", " ").title()
        else:
            customer_name = "New Customer"

        profile = CRMProfile(
            customer_id=f"new_{identifier}",
            customer_name=customer_name,
            customer_tier="regular",
            subscription_plan=None,
            account_age_days=0,
            email=identifier if identifier_type == "email" else None,
            phone=identifier if identifier_type == "phone" else None,
            created_at=datetime.now(UTC),
            raw_crm_data={"is_minimal": True},
        )

        logger.info(f"Created minimal profile for {identifier}")
        return profile

    async def fetch_profile_by_email(
        self,
        email: str,
        crm_client: Optional[Any] = None,
    ) -> CRMProfile:
        """
        Fetch customer profile by email.

        Args:
            email: Email address
            crm_client: CRM client (optional, for actual CRM query)

        Returns:
            CRM profile
        """
        # Check cache first
        cached_profile = await self._get_cached_profile(email)
        if cached_profile:
            return cached_profile

        # Fetch from CRM (placeholder - requires actual CRM client)
        if crm_client:
            # TODO: Implement actual CRM query
            crm_data = {}
            # crm_data = await crm_client.get_contact_by_email(email)
        else:
            # Placeholder data for testing
            crm_data = {
                "id": "placeholder_id",
                "first_name": "Test",
                "last_name": "User",
                "email": email,
                "tier": "regular",
                "subscription_plan": "basic",
                "created_at": "2024-01-01T00:00:00Z",
            }

        # Handle missing customer
        if not crm_data or not crm_data.get("id"):
            profile = self._create_minimal_profile(email, "email")
        else:
            profile = self._map_crm_fields_to_profile(crm_data)

        # Apply field-level security
        profile = self._apply_field_security(profile)

        # Cache the profile
        await self._cache_profile(email, profile)

        return profile

    async def fetch_profile_by_phone(
        self,
        phone: str,
        crm_client: Optional[Any] = None,
    ) -> CRMProfile:
        """
        Fetch customer profile by phone number.

        Args:
            phone: Phone number
            crm_client: CRM client (optional, for actual CRM query)

        Returns:
            CRM profile
        """
        # Check cache first
        cached_profile = await self._get_cached_profile(phone)
        if cached_profile:
            return cached_profile

        # Fetch from CRM (placeholder - requires actual CRM client)
        if crm_client:
            # TODO: Implement actual CRM query
            crm_data = {}
            # crm_data = await crm_client.get_contact_by_phone(phone)
        else:
            # Placeholder data for testing
            crm_data = {
                "id": "placeholder_id",
                "first_name": "Test",
                "last_name": "User",
                "phone": phone,
                "tier": "regular",
                "subscription_plan": "basic",
                "created_at": "2024-01-01T00:00:00Z",
            }

        # Handle missing customer
        if not crm_data or not crm_data.get("id"):
            profile = self._create_minimal_profile(phone, "phone")
        else:
            profile = self._map_crm_fields_to_profile(crm_data)

        # Apply field-level security
        profile = self._apply_field_security(profile)

        # Cache the profile
        await self._cache_profile(phone, profile)

        return profile

    async def invalidate_profile_cache(self, identifier: str) -> None:
        """
        Invalidate profile cache.

        Args:
            identifier: Email or phone number
        """
        await self._invalidate_cache(identifier)
