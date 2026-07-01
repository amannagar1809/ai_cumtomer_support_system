"""TLS configuration for secure data in transit."""

import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class TLSConfig:
    """TLS configuration for secure connections."""

    @staticmethod
    def get_ssl_context():
        """
        Get SSL context for TLS 1.3.

        Returns:
            SSL context or None if TLS is disabled
        """
        if not settings.tls_enabled:
            logger.warning("TLS is disabled")
            return None

        try:
            import ssl

            # Create SSL context with TLS 1.3
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

            # Set minimum TLS version to 1.3
            context.minimum_version = ssl.TLSVersion.TLSv1_3

            # Set strong cipher suites
            context.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256")

            # Load certificate and key if provided
            if settings.tls_cert_file and settings.tls_key_file:
                cert_file = Path(settings.tls_cert_file)
                key_file = Path(settings.tls_key_file)

                if cert_file.exists() and key_file.exists():
                    context.load_cert_chain(
                        certfile=str(cert_file),
                        keyfile=str(key_file),
                    )
                    logger.info(f"Loaded TLS certificate from {cert_file}")
                else:
                    logger.warning(
                        f"TLS certificate or key file not found: {cert_file}, {key_file}"
                    )
            else:
                logger.warning("TLS certificate and key files not configured")

            # Enable HSTS (HTTP Strict Transport Security)
            # This should be set in the web server configuration

            return context

        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            return None

    @staticmethod
    def get_uvicorn_ssl_config():
        """
        Get SSL configuration for uvicorn.

        Returns:
            Dictionary with SSL configuration or None
        """
        if not settings.tls_enabled:
            return None

        if settings.tls_cert_file and settings.tls_key_file:
            cert_file = Path(settings.tls_cert_file)
            key_file = Path(settings.tls_key_file)

            if cert_file.exists() and key_file.exists():
                return {
                    "ssl_keyfile": str(key_file),
                    "ssl_certfile": str(cert_file),
                    "ssl_version": settings.tls_min_version,
                }
            else:
                logger.warning(
                    f"TLS certificate or key file not found: {cert_file}, {key_file}"
                )
                return None

        logger.warning("TLS certificate and key files not configured")
        return None

    @staticmethod
    def validate_tls_config() -> dict:
        """
        Validate TLS configuration.

        Returns:
            Dictionary with validation results
        """
        results = {
            "tls_enabled": settings.tls_enabled,
            "tls_min_version": settings.tls_min_version,
            "certificate_configured": False,
            "key_configured": False,
            "certificate_exists": False,
            "key_exists": False,
            "tls_13_supported": False,
        }

        if not settings.tls_enabled:
            return results

        # Check if TLS 1.3 is supported
        try:
            import ssl

            if hasattr(ssl, "TLSVersion") and hasattr(ssl.TLSVersion, "TLSv1_3"):
                results["tls_13_supported"] = True
        except Exception:
            pass

        # Check certificate and key configuration
        if settings.tls_cert_file:
            results["certificate_configured"] = True
            cert_file = Path(settings.tls_cert_file)
            results["certificate_exists"] = cert_file.exists()

        if settings.tls_key_file:
            results["key_configured"] = True
            key_file = Path(settings.tls_key_file)
            results["key_exists"] = key_file.exists()

        return results

    @staticmethod
    def get_hsts_header(max_age: int = 31536000, include_subdomains: bool = True, preload: bool = False) -> str:
        """
        Get HSTS header value.

        Args:
            max_age: Max age in seconds (default: 1 year)
            include_subdomains: Include subdomains
            preload: Include preload directive

        Returns:
            HSTS header value
        """
        header = f"max-age={max_age}"

        if include_subdomains:
            header += "; includeSubDomains"

        if preload:
            header += "; preload"

        return header


# Global TLS configuration
tls_config = TLSConfig()
