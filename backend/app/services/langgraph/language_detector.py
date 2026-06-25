"""Language detection service using fastText for multi-language support."""

import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "de": "German",
}

# Language code to ISO 639-1 mapping
LANGUAGE_CODES = {
    "english": "en",
    "hindi": "hi",
    "spanish": "es",
    "french": "fr",
    "arabic": "ar",
    "german": "de",
}

# Confidence threshold for language detection
CONFIDENCE_THRESHOLD = 0.85

# Performance target in milliseconds
PERFORMANCE_TARGET_MS = 100

# Default fallback language
DEFAULT_LANGUAGE = "en"

# Cache TTL in seconds (1 hour)
CACHE_TTL_SECONDS = 3600


class LanguageDetectionResult(BaseModel):
    """Result of language detection."""

    detected_language: str = Field(description="Detected language code (e.g., 'en', 'hi')")
    language_name: str = Field(description="Full language name (e.g., 'English', 'Hindi')")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    is_supported: bool = Field(description="Whether the detected language is supported")
    is_fallback: bool = Field(default=False, description="Whether fallback to default language was used")
    detection_time_ms: float = Field(description="Time taken for detection in milliseconds")
    from_cache: bool = Field(default=False, description="Whether result was retrieved from cache")


class LanguageDetector:
    """Language detection service using fastText."""

    def __init__(self):
        """Initialize language detector."""
        self.logger = logger
        self.model = None
        self._cache = {}  # Simple in-memory cache (user_id -> (language, confidence, timestamp))
        self._load_model()

    def _load_model(self):
        """Load fastText language detection model."""
        try:
            # Placeholder for fastText model loading
            # In production, this would load the actual fastText model
            # For now, we'll use a simple rule-based approach as placeholder
            logger.info("Language detector initialized (placeholder mode)")
            self.model = "placeholder"
        except Exception as e:
            logger.error(f"Failed to load language detection model: {e}")
            self.model = None

    def detect_language(
        self,
        text: str,
        user_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> LanguageDetectionResult:
        """
        Detect language of the given text.

        Args:
            text: Text to detect language from
            user_id: User ID for caching (assumes same language per conversation)
            use_cache: Whether to use cached results

        Returns:
            Language detection result
        """
        start_time = time.time()

        # Check cache first if user_id provided
        if use_cache and user_id:
            cached_result = self._get_from_cache(user_id)
            if cached_result:
                detection_time_ms = (time.time() - start_time) * 1000
                cached_result.detection_time_ms = detection_time_ms
                cached_result.from_cache = True
                logger.info(f"Language detection from cache for user {user_id}: {cached_result.detected_language}")
                return cached_result

        # Perform language detection
        result = self._detect_language_internal(text)

        # Cache result if user_id provided
        if user_id and result.is_supported:
            self._add_to_cache(user_id, result)

        detection_time_ms = (time.time() - start_time) * 1000
        result.detection_time_ms = detection_time_ms

        # Log performance
        if detection_time_ms > PERFORMANCE_TARGET_MS:
            logger.warning(f"Language detection took {detection_time_ms:.2f}ms (target: {PERFORMANCE_TARGET_MS}ms)")
        else:
            logger.debug(f"Language detection took {detection_time_ms:.2f}ms")

        logger.info(
            f"Language detected: {result.language_name} "
            f"(confidence: {result.confidence:.2f}, supported: {result.is_supported})"
        )

        return result

    def _detect_language_internal(self, text: str) -> LanguageDetectionResult:
        """
        Internal language detection logic.

        Args:
            text: Text to detect language from

        Returns:
            Language detection result
        """
        if not text or len(text.strip()) < 3:
            # Too short to detect, use default
            return LanguageDetectionResult(
                detected_language=DEFAULT_LANGUAGE,
                language_name=SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE],
                confidence=0.0,
                is_supported=True,
                is_fallback=True,
                detection_time_ms=0.0,
            )

        # Placeholder detection logic
        # In production, this would use fastText or cld3
        detected_lang, confidence = self._detect_with_placeholder(text)

        # Check if language is supported
        is_supported = detected_lang in SUPPORTED_LANGUAGES

        # Check confidence threshold
        if confidence < CONFIDENCE_THRESHOLD or not is_supported:
            # Fallback to default language
            return LanguageDetectionResult(
                detected_language=DEFAULT_LANGUAGE,
                language_name=SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE],
                confidence=0.0,
                is_supported=True,
                is_fallback=True,
                detection_time_ms=0.0,
            )

        return LanguageDetectionResult(
            detected_language=detected_lang,
            language_name=SUPPORTED_LANGUAGES[detected_lang],
            confidence=confidence,
            is_supported=True,
            is_fallback=False,
            detection_time_ms=0.0,
        )

    def _detect_with_placeholder(self, text: str) -> tuple[str, float]:
        """
        Placeholder language detection using simple heuristics.

        In production, replace with actual fastText/cld3 implementation.

        Args:
            text: Text to detect language from

        Returns:
            Tuple of (language_code, confidence)
        """
        text_lower = text.lower()

        # Simple heuristic-based detection (placeholder)
        # In production, use actual fastText model
        if any(char in text for char in "अआइईउऊऋएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह"):
            return "hi", 0.95  # Hindi
        elif any(char in text for char in "ñáéíóúü¿¡"):
            return "es", 0.90  # Spanish
        elif any(char in text for char in "àâäéèêëïîôùûüÿçœæ"):
            return "fr", 0.90  # French
        elif any(char in text for char in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"):
            return "ar", 0.95  # Arabic
        elif any(char in text for char in "äöüßÄÖÜẞ"):
            return "de", 0.90  # German
        else:
            return "en", 0.85  # English (default)

    def _get_from_cache(self, user_id: str) -> Optional[LanguageDetectionResult]:
        """
        Get language detection result from cache.

        Args:
            user_id: User ID

        Returns:
            Cached result if valid, None otherwise
        """
        if user_id not in self._cache:
            return None

        cached_data, timestamp = self._cache[user_id]
        cache_age = time.time() - timestamp

        # Check if cache is still valid
        if cache_age > CACHE_TTL_SECONDS:
            del self._cache[user_id]
            logger.debug(f"Cache expired for user {user_id}")
            return None

        logger.debug(f"Cache hit for user {user_id} (age: {cache_age:.0f}s)")
        return cached_data

    def _add_to_cache(self, user_id: str, result: LanguageDetectionResult):
        """
        Add language detection result to cache.

        Args:
            user_id: User ID
            result: Detection result to cache
        """
        self._cache[user_id] = (result, time.time())
        logger.debug(f"Cached language detection for user {user_id}: {result.detected_language}")

    def clear_cache(self, user_id: Optional[str] = None):
        """
        Clear language detection cache.

        Args:
            user_id: Specific user ID to clear, or None to clear all
        """
        if user_id:
            if user_id in self._cache:
                del self._cache[user_id]
                logger.debug(f"Cleared cache for user {user_id}")
        else:
            self._cache.clear()
            logger.debug("Cleared all language detection cache")

    def get_supported_languages(self) -> dict[str, str]:
        """
        Get list of supported languages.

        Returns:
            Dictionary of language codes to language names
        """
        return SUPPORTED_LANGUAGES.copy()

    def is_language_supported(self, language_code: str) -> bool:
        """
        Check if a language is supported.

        Args:
            language_code: Language code to check

        Returns:
            True if language is supported
        """
        return language_code in SUPPORTED_LANGUAGES
