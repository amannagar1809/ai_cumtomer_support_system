"""Encrypted fields mixin for SQLAlchemy models."""

from typing import Optional

from sqlalchemy import String, event
from sqlalchemy.orm import MapperExtension, mapper

from app.core.encryption import encryption_service


class EncryptedMixin:
    """Mixin for models with encrypted fields."""

    # Override these in the model
    _encrypted_fields = []

    def encrypt_field(self, field_name: str, value: Optional[str], tenant_id: Optional[str] = None) -> Optional[str]:
        """
        Encrypt a field value.

        Args:
            field_name: Name of the field
            value: Value to encrypt
            tenant_id: Tenant ID for multi-tenant encryption

        Returns:
            Encrypted value or None if value is None
        """
        if value is None:
            return None
        return encryption_service.encrypt(value, tenant_id=tenant_id)

    def decrypt_field(self, field_name: str, value: Optional[str], tenant_id: Optional[str] = None) -> Optional[str]:
        """
        Decrypt a field value.

        Args:
            field_name: Name of the field
            value: Value to decrypt
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Decrypted value or None if value is None
        """
        if value is None:
            return None
        try:
            return encryption_service.decrypt(value, tenant_id=tenant_id)
        except Exception:
            return value  # Return original if decryption fails

    def get_encrypted_data(self, tenant_id: Optional[str] = None) -> dict:
        """
        Get all encrypted fields with decrypted values.

        Args:
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Dictionary of field names and decrypted values
        """
        encrypted_data = {}
        for field_name in self._encrypted_fields:
            if hasattr(self, field_name):
                encrypted_value = getattr(self, field_name)
                decrypted_value = self.decrypt_field(field_name, encrypted_value, tenant_id)
                encrypted_data[field_name] = decrypted_value
        return encrypted_data

    def set_encrypted_data(self, data: dict, tenant_id: Optional[str] = None):
        """
        Set encrypted fields from a dictionary.

        Args:
            data: Dictionary of field names and plaintext values
            tenant_id: Tenant ID for multi-tenant encryption
        """
        for field_name, value in data.items():
            if field_name in self._encrypted_fields and hasattr(self, field_name):
                encrypted_value = self.encrypt_field(field_name, value, tenant_id)
                setattr(self, field_name, encrypted_value)


class EncryptedUserMixin(EncryptedMixin):
    """Mixin for user models with PII encryption."""

    _encrypted_fields = ["encrypted_email", "encrypted_phone", "encrypted_name"]

    @property
    def decrypted_email(self) -> Optional[str]:
        """Get decrypted email."""
        return self.decrypt_field("encrypted_email", getattr(self, "encrypted_email", None))

    @property
    def decrypted_phone(self) -> Optional[str]:
        """Get decrypted phone."""
        return self.decrypt_field("encrypted_phone", getattr(self, "encrypted_phone", None))

    @property
    def decrypted_name(self) -> Optional[str]:
        """Get decrypted name."""
        return self.decrypt_field("encrypted_name", getattr(self, "encrypted_name", None))

    def set_email(self, email: Optional[str], tenant_id: Optional[str] = None):
        """Set encrypted email."""
        self.encrypted_email = self.encrypt_field("encrypted_email", email, tenant_id)

    def set_phone(self, phone: Optional[str], tenant_id: Optional[str] = None):
        """Set encrypted phone."""
        self.encrypted_phone = self.encrypt_field("encrypted_phone", phone, tenant_id)

    def set_name(self, name: Optional[str], tenant_id: Optional[str] = None):
        """Set encrypted name."""
        self.encrypted_name = self.encrypt_field("encrypted_name", name, tenant_id)
