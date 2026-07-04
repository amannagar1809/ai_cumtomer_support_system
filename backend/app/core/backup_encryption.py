"""Database backup encryption service."""

import gzip
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.encryption import encryption_service

logger = logging.getLogger(__name__)


class BackupEncryptionService:
    """Service for encrypting database backups."""

    def __init__(self):
        """Initialize backup encryption service."""
        self.backup_dir = Path(settings.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def encrypt_backup(
        self,
        backup_file: Path,
        output_file: Optional[Path] = None,
        tenant_id: Optional[str] = None,
    ) -> Path:
        """
        Encrypt a database backup file.

        Args:
            backup_file: Path to backup file to encrypt
            output_file: Path to output encrypted file (default: backup_file.enc)
            tenant_id: Tenant ID for multi-tenant encryption

        Returns:
            Path to encrypted backup file
        """
        try:
            if output_file is None:
                output_file = backup_file.with_suffix(backup_file.suffix + ".enc")

            # Read backup file
            with open(backup_file, "rb") as f:
                backup_data = f.read()

            # Compress backup data
            compressed_data = gzip.compress(backup_data)

            # Encrypt compressed data
            encrypted_data = encryption_service.encrypt(
                compressed_data.decode("latin-1"),
                tenant_id=tenant_id,
            )

            # Write encrypted data
            with open(output_file, "wb") as f:
                f.write(encrypted_data.encode("latin-1"))

            # Delete original backup file
            backup_file.unlink()

            self.logger.info(f"Backup encrypted: {backup_file} -> {output_file}")
            return output_file

        except Exception as e:
            self.logger.error(f"Failed to encrypt backup {backup_file}: {e}")
            raise

    def decrypt_backup(
        self,
        encrypted_file: Path,
        output_file: Optional[Path] = None,
        tenant_id: Optional[str] = None,
    ) -> Path:
        """
        Decrypt a database backup file.

        Args:
            encrypted_file: Path to encrypted backup file
            output_file: Path to output decrypted file (default: remove .enc suffix)
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Path to decrypted backup file
        """
        try:
            if output_file is None:
                output_file = encrypted_file.with_suffix(
                    encrypted_file.suffix.replace(".enc", "")
                )

            # Read encrypted file
            with open(encrypted_file, "rb") as f:
                encrypted_data = f.read().decode("latin-1")

            # Decrypt data
            decrypted_data = encryption_service.decrypt(
                encrypted_data,
                tenant_id=tenant_id,
            )

            # Decompress data
            compressed_data = decrypted_data.encode("latin-1")
            backup_data = gzip.decompress(compressed_data)

            # Write decrypted data
            with open(output_file, "wb") as f:
                f.write(backup_data)

            self.logger.info(f"Backup decrypted: {encrypted_file} -> {output_file}")
            return output_file

        except Exception as e:
            self.logger.error(f"Failed to decrypt backup {encrypted_file}: {e}")
            raise

    def encrypt_backup_stream(
        self,
        backup_data: bytes,
        tenant_id: Optional[str] = None,
    ) -> bytes:
        """
        Encrypt backup data from stream.

        Args:
            backup_data: Backup data to encrypt
            tenant_id: Tenant ID for multi-tenant encryption

        Returns:
            Encrypted backup data
        """
        try:
            # Compress backup data
            compressed_data = gzip.compress(backup_data)

            # Encrypt compressed data
            encrypted_data = encryption_service.encrypt(
                compressed_data.decode("latin-1"),
                tenant_id=tenant_id,
            )

            return encrypted_data.encode("latin-1")

        except Exception as e:
            self.logger.error(f"Failed to encrypt backup stream: {e}")
            raise

    def decrypt_backup_stream(
        self,
        encrypted_data: bytes,
        tenant_id: Optional[str] = None,
    ) -> bytes:
        """
        Decrypt backup data from stream.

        Args:
            encrypted_data: Encrypted backup data
            tenant_id: Tenant ID for multi-tenant decryption

        Returns:
            Decrypted backup data
        """
        try:
            # Decrypt data
            decrypted_data = encryption_service.decrypt(
                encrypted_data.decode("latin-1"),
                tenant_id=tenant_id,
            )

            # Decompress data
            compressed_data = decrypted_data.encode("latin-1")
            backup_data = gzip.decompress(compressed_data)

            return backup_data

        except Exception as e:
            self.logger.error(f"Failed to decrypt backup stream: {e}")
            raise

    def list_encrypted_backups(self) -> list[Path]:
        """
        List all encrypted backup files.

        Returns:
            List of encrypted backup file paths
        """
        try:
            encrypted_files = list(self.backup_dir.glob("*.enc"))
            return encrypted_files
        except Exception as e:
            self.logger.error(f"Failed to list encrypted backups: {e}")
            return []

    def cleanup_old_backups(self, retention_days: Optional[int] = None) -> int:
        """
        Delete old encrypted backups beyond retention period.

        Args:
            retention_days: Retention period in days (default: from config)

        Returns:
            Number of backups deleted
        """
        try:
            if retention_days is None:
                retention_days = settings.backup_retention_days

            cutoff_date = datetime.utcnow().timestamp() - (retention_days * 86400)
            deleted_count = 0

            for backup_file in self.list_encrypted_backups():
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    self.logger.info(f"Deleted old backup: {backup_file}")

            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old backups: {e}")
            return 0


# Global backup encryption service instance
backup_encryption_service = BackupEncryptionService()
