"""Key Management Service (KMS) integration for secure key storage."""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class KMSProvider:
    """Base class for KMS providers."""

    async def get_key(self, key_id: str) -> Optional[str]:
        """
        Get encryption key from KMS.

        Args:
            key_id: Key identifier

        Returns:
            Encryption key or None if not found
        """
        raise NotImplementedError

    async def generate_key(self, key_id: str) -> str:
        """
        Generate new encryption key in KMS.

        Args:
            key_id: Key identifier

        Returns:
            Generated key
        """
        raise NotImplementedError

    async def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in KMS.

        Args:
            key_id: Key identifier

        Returns:
            New key
        """
        raise NotImplementedError

    async def delete_key(self, key_id: str) -> bool:
        """
        Delete encryption key from KMS.

        Args:
            key_id: Key identifier

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError


class AWSKMSProvider(KMSProvider):
    """AWS KMS provider."""

    def __init__(self):
        """Initialize AWS KMS provider."""
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize AWS KMS client."""
        try:
            import boto3

            self.client = boto3.client(
                "kms",
                region_name=settings.aws_kms_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            logger.info("AWS KMS client initialized")
        except ImportError:
            logger.warning("boto3 not installed, AWS KMS not available")
        except Exception as e:
            logger.error(f"Failed to initialize AWS KMS client: {e}")

    async def get_key(self, key_id: str) -> Optional[str]:
        """
        Get encryption key from AWS KMS.

        Args:
            key_id: Key identifier (KMS key ARN or alias)

        Returns:
            Encryption key or None if not found
        """
        if not self.client:
            return None

        try:
            response = self.client.generate_data_key(
                KeyId=key_id,
                KeySpec="AES_256",
            )
            return response["Plaintext"].hex()
        except Exception as e:
            logger.error(f"Failed to get key from AWS KMS: {e}")
            return None

    async def generate_key(self, key_id: str) -> str:
        """
        Generate new encryption key in AWS KMS.

        Args:
            key_id: Key identifier

        Returns:
            Generated key
        """
        if not self.client:
            raise Exception("AWS KMS client not available")

        try:
            response = self.client.create_key(
                Description=f"Encryption key for {key_id}",
                KeyUsage="ENCRYPT_DECRYPT",
                Origin="AWS_KMS",
            )
            return response["KeyMetadata"]["Arn"]
        except Exception as e:
            logger.error(f"Failed to generate key in AWS KMS: {e}")
            raise

    async def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in AWS KMS.

        Args:
            key_id: Key identifier

        Returns:
            New key ARN
        """
        if not self.client:
            raise Exception("AWS KMS client not available")

        try:
            # Enable key rotation
            self.client.enable_key_rotation(KeyId=key_id)

            # Schedule immediate rotation
            response = self.client.rotate_key_on_demand(KeyId=key_id)
            return response["KeyMetadata"]["Arn"]
        except Exception as e:
            logger.error(f"Failed to rotate key in AWS KMS: {e}")
            raise

    async def delete_key(self, key_id: str) -> bool:
        """
        Delete encryption key from AWS KMS.

        Args:
            key_id: Key identifier

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            # Schedule key deletion (7-30 days waiting period)
            self.client.schedule_key_deletion(
                KeyId=key_id,
                PendingWindowInDays=7,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete key from AWS KMS: {e}")
            return False


class HashiCorpVaultProvider(KMSProvider):
    """HashiCorp Vault provider."""

    def __init__(self):
        """Initialize HashiCorp Vault provider."""
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize HashiCorp Vault client."""
        try:
            import hvac

            self.client = hvac.Client(
                url=settings.vault_url,
                token=settings.vault_token,
            )
            logger.info("HashiCorp Vault client initialized")
        except ImportError:
            logger.warning("hvac not installed, HashiCorp Vault not available")
        except Exception as e:
            logger.error(f"Failed to initialize HashiCorp Vault client: {e}")

    async def get_key(self, key_id: str) -> Optional[str]:
        """
        Get encryption key from HashiCorp Vault.

        Args:
            key_id: Key identifier (path in Vault)

        Returns:
            Encryption key or None if not found
        """
        if not self.client:
            return None

        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=key_id)
            return response["data"]["data"]["key"]
        except Exception as e:
            logger.error(f"Failed to get key from HashiCorp Vault: {e}")
            return None

    async def generate_key(self, key_id: str) -> str:
        """
        Generate new encryption key in HashiCorp Vault.

        Args:
            key_id: Key identifier (path in Vault)

        Returns:
            Generated key
        """
        if not self.client:
            raise Exception("HashiCorp Vault client not available")

        try:
            import secrets

            new_key = secrets.token_urlsafe(32)

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key_id,
                secret={"key": new_key},
            )

            return new_key
        except Exception as e:
            logger.error(f"Failed to generate key in HashiCorp Vault: {e}")
            raise

    async def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in HashiCorp Vault.

        Args:
            key_id: Key identifier (path in Vault)

        Returns:
            New key
        """
        if not self.client:
            raise Exception("HashiCorp Vault client not available")

        try:
            import secrets

            new_key = secrets.token_urlsafe(32)

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key_id,
                secret={"key": new_key},
            )

            return new_key
        except Exception as e:
            logger.error(f"Failed to rotate key in HashiCorp Vault: {e}")
            raise

    async def delete_key(self, key_id: str) -> bool:
        """
        Delete encryption key from HashiCorp Vault.

        Args:
            key_id: Key identifier (path in Vault)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=key_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key from HashiCorp Vault: {e}")
            return False


class KMSService:
    """Service for managing encryption keys via KMS."""

    def __init__(self):
        """Initialize KMS service."""
        self.provider: Optional[KMSProvider] = None
        self._initialize_provider()
        self.logger = logger

    def _initialize_provider(self):
        """Initialize KMS provider based on configuration."""
        provider_type = settings.kms_provider.lower() if settings.kms_provider else "local"

        if provider_type == "aws":
            self.provider = AWSKMSProvider()
        elif provider_type == "vault":
            self.provider = HashiCorpVaultProvider()
        else:
            logger.info("Using local key storage (no KMS provider configured)")

    async def get_master_key(self) -> str:
        """
        Get master encryption key.

        Returns:
            Master encryption key
        """
        if self.provider:
            key = await self.provider.get_key(settings.kms_master_key_id or "master")
            if key:
                return key

        # Fallback to config
        return settings.encryption_master_key

    async def generate_master_key(self) -> str:
        """
        Generate new master encryption key.

        Returns:
            New master key
        """
        if self.provider:
            return await self.provider.generate_key(settings.kms_master_key_id or "master")

        # Fallback to local generation
        from app.core.encryption import encryption_service
        return encryption_service.generate_key()

    async def rotate_master_key(self) -> str:
        """
        Rotate master encryption key.

        Returns:
            New master key
        """
        if self.provider:
            return await self.provider.rotate_key(settings.kms_master_key_id or "master")

        # Fallback to local rotation
        from app.core.encryption import encryption_service
        new_key = encryption_service.generate_key()
        old_key = settings.encryption_master_key
        encryption_service.rotate_key(old_key, new_key)
        return new_key

    async def delete_master_key(self) -> bool:
        """
        Delete master encryption key.

        Returns:
            True if successful, False otherwise
        """
        if self.provider:
            return await self.provider.delete_key(settings.kms_master_key_id or "master")

        logger.warning("Cannot delete local key from config")
        return False


# Global KMS service instance
kms_service = KMSService()
