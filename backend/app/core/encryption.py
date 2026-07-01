"""Encryption service for sensitive data using AES-256."""

import base64
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256."""

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            master_key: Master encryption key (from KMS/HSM or config)
        """
        self.master_key = master_key or settings.encryption_master_key
        self.key_cache = {}  # Cache for tenant-specific keys
        self.logger = logger

    def _generate_key_from_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
    ) -> bytes:
        """
        Generate encryption key from password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation (generated if not provided)

        Returns:
            Tuple of (key, salt)
        """
        if salt is None:
            salt = base64.urlsafe_b64encode(hashlib.sha256().digest())

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    def _get_tenant_key(self, tenant_id: Optional[str] = None) -> Fernet:
        """
        Get encryption key for a tenant.

        Args:
            tenant_id: Tenant ID (uses master key if None)

        Returns:
            Fernet cipher for encryption/decryption
        """
        if tenant_id is None:
            # Use master key for single-tenant or default
            if "default" not in self.key_cache:
                key, _ = self._generate_key_from_password(self.master_key)
                self.key_cache["default"] = Fernet(key)
            return self.key_cache["default"]

        # Generate tenant-specific key
        if tenant_id not in self.key_cache:
            # Derive tenant-specific key from master key + tenant_id
            tenant_password = f"{self.master_key}:{tenant_id}"
            key, _ = self._generate_key_from_password(tenant_password)
            self.key_cache[tenant_id] = Fernet(key)

        return self.key_cache[tenant_id]

    def encrypt(
        self,
        plaintext: str,
        tenant_id: Optional[str] = None,
    ) -> str:
        """
        Encrypt plaintext using AES-256.

        Args:
            plaintext: Text to encrypt
            tenant_id: Tenant ID for multi-tenant encryption

        Returns:
            Encrypted text (base64 encoded)
        """
        try:
            cipher = self._get_tenant_key(tenant_id)
            encrypted_bytes = cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(
        self,
        ciphertext: str,
        tenant_id: Optional[str] = None,
    ) -> str:
        """
        Decrypt ciphertext using AES-256.

        Args:
            ciphertext: Encrypted text (base64 encoded)
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Decrypted plaintext
        """
        try:
            cipher = self._get_tenant_key(tenant_id)
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_pii(
        self,
        pii_data: dict,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """
        Encrypt PII fields in a dictionary.

        Args:
            pii_data: Dictionary containing PII fields
            tenant_id: Tenant ID for multi-tenant encryption

        Returns:
            Dictionary with encrypted PII fields
        """
        encrypted_data = pii_data.copy()

        # Fields to encrypt
        pii_fields = ["email", "phone", "name", "first_name", "last_name", "address"]

        for field in pii_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(
                    str(encrypted_data[field]),
                    tenant_id=tenant_id,
                )

        return encrypted_data

    def decrypt_pii(
        self,
        encrypted_data: dict,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """
        Decrypt PII fields in a dictionary.

        Args:
            encrypted_data: Dictionary containing encrypted PII fields
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Dictionary with decrypted PII fields
        """
        decrypted_data = encrypted_data.copy()

        # Fields to decrypt
        pii_fields = ["email", "phone", "name", "first_name", "last_name", "address"]

        for field in pii_fields:
            if field in decrypted_data and decrypted_data[field]:
                try:
                    decrypted_data[field] = self.decrypt(
                        str(decrypted_data[field]),
                        tenant_id=tenant_id,
                    )
                except Exception:
                    # If decryption fails, keep original value
                    # (might be already decrypted or not encrypted)
                    pass

        return decrypted_data

    def rotate_key(
        self,
        old_key: str,
        new_key: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Rotate encryption key.

        Args:
            old_key: Old encryption key
            new_key: New encryption key
            tenant_id: Tenant ID for multi-tenant key rotation

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove old key from cache
            cache_key = tenant_id if tenant_id else "default"
            if cache_key in self.key_cache:
                del self.key_cache[cache_key]

            # Update master key
            if tenant_id is None:
                self.master_key = new_key

            # Generate new cipher with new key
            cipher = self._get_tenant_key(tenant_id)

            self.logger.info(f"Encryption key rotated for {cache_key}")
            return True

        except Exception as e:
            self.logger.error(f"Key rotation failed: {e}")
            return False

    def generate_key(self) -> str:
        """
        Generate a new encryption key.

        Returns:
            Base64 encoded encryption key
        """
        return Fernet.generate_key().decode()


# Global encryption service instance
encryption_service = EncryptionService()
