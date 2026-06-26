"""Document translation service for knowledge base multi-language support."""

import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

from app.services.langgraph.translation_service import TranslationService

logger = logging.getLogger(__name__)

# Translation note for fallback to English
TRANSLATION_NOTE = {
    "en": "",
    "hi": " (अंग्रेजी से अनुवादित)",
    "es": " (traducido del inglés)",
    "fr": " (traduit de l'anglais)",
    "ar": " (مترجم من الإنجليزية)",
    "de": " (aus dem Englischen übersetzt)",
}


class DocumentTranslationResult(BaseModel):
    """Result of document translation operation."""

    original_document_id: str = Field(description="Original document ID")
    translated_title: str = Field(description="Translated title")
    translated_content: str = Field(description="Translated content")
    source_language: str = Field(description="Source language code")
    target_language: str = Field(description="Target language code")
    success: bool = Field(description="Whether translation was successful")
    error: Optional[str] = Field(default=None, description="Error message if translation failed")
    translation_time_ms: float = Field(description="Time taken for translation in milliseconds")
    confidence: float = Field(description="Translation confidence score (0.0 to 1.0)")


class DocumentTranslator:
    """Service for translating knowledge base documents."""

    def __init__(self):
        """Initialize document translator."""
        self.logger = logger
        self.translation_service = TranslationService()

    def translate_document(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
    ) -> DocumentTranslationResult:
        """
        Translate a knowledge base document.

        Args:
            title: Document title
            content: Document content
            source_language: Source language code
            target_language: Target language code

        Returns:
            Document translation result
        """
        start_time = time.time()

        # Skip translation if source and target are the same
        if source_language == target_language:
            return DocumentTranslationResult(
                original_document_id="",
                translated_title=title,
                translated_content=content,
                source_language=source_language,
                target_language=target_language,
                success=True,
                translation_time_ms=0.0,
                confidence=1.0,
            )

        try:
            # Translate title
            title_result = self.translation_service.translate(
                text=title,
                source_language=source_language,
                target_language=target_language,
            )

            # Translate content
            content_result = self.translation_service.translate(
                text=content,
                source_language=source_language,
                target_language=target_language,
            )

            translation_time_ms = (time.time() - start_time) * 1000

            if title_result.success and content_result.success:
                result = DocumentTranslationResult(
                    original_document_id="",
                    translated_title=title_result.translated_text,
                    translated_content=content_result.translated_text,
                    source_language=source_language,
                    target_language=target_language,
                    success=True,
                    translation_time_ms=translation_time_ms,
                    confidence=0.9,  # Placeholder confidence score
                )

                logger.info(
                    f"Document translation successful: {source_language} -> {target_language}, "
                    f"time: {translation_time_ms:.2f}ms"
                )

                return result
            else:
                # Translation failed
                error_msg = "Translation failed"
                if not title_result.success:
                    error_msg += f" (title: {title_result.error})"
                if not content_result.success:
                    error_msg += f" (content: {content_result.error})"

                result = DocumentTranslationResult(
                    original_document_id="",
                    translated_title=title,
                    translated_content=content,
                    source_language=source_language,
                    target_language=target_language,
                    success=False,
                    error=error_msg,
                    translation_time_ms=translation_time_ms,
                    confidence=0.0,
                )

                logger.error(f"Document translation failed: {error_msg}")

                return result

        except Exception as e:
            translation_time_ms = (time.time() - start_time) * 1000

            result = DocumentTranslationResult(
                original_document_id="",
                translated_title=title,
                translated_content=content,
                source_language=source_language,
                target_language=target_language,
                success=False,
                error=str(e),
                translation_time_ms=translation_time_ms,
                confidence=0.0,
            )

            logger.error(f"Document translation error: {e}")

            return result

    def translate_to_supported_languages(
        self,
        title: str,
        content: str,
        source_language: str = "en",
    ) -> dict[str, DocumentTranslationResult]:
        """
        Translate document to all supported languages.

        Args:
            title: Document title
            content: Document content
            source_language: Source language code (default: English)

        Returns:
            Dictionary of language codes to translation results
        """
        from app.services.langgraph.language_detector import SUPPORTED_LANGUAGES

        results = {}

        for lang_code in SUPPORTED_LANGUAGES.keys():
            if lang_code == source_language:
                # Skip source language
                continue

            result = self.translate_document(
                title=title,
                content=content,
                source_language=source_language,
                target_language=lang_code,
            )

            results[lang_code] = result

        return results

    def get_translation_note(self, target_language: str) -> str:
        """
        Get translation note for fallback to English.

        Args:
            target_language: Target language code

        Returns:
            Translation note in the target language
        """
        return TRANSLATION_NOTE.get(target_language, "")
