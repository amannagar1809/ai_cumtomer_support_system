"""Translation service for multi-language support."""

import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Target language for AI processing
TARGET_LANGUAGE = "en"

# Translation service types
TRANSLATION_SERVICE_GOOGLE = "google"
TRANSLATION_SERVICE_DEEPL = "deepl"
TRANSLATION_SERVICE_NLLB = "nllb"

# Apology message for translation failures
TRANSLATION_FAILURE_APOLOGY = {
    "en": "I apologize, but I encountered an error translating the response. Here is the response in English:",
    "hi": "मुझे खेद है, लेकिन मुझे प्रतिक्रिया अनुवाद करने में त्रुटि हुई। यहाँ अंग्रेजी में प्रतिक्रिया है:",
    "es": "Lamento, pero encontré un error al traducir la respuesta. Aquí está la respuesta en inglés:",
    "fr": "Je suis désolé, mais j'ai rencontré une erreur lors de la traduction de la réponse. Voici la réponse en anglais:",
    "ar": "أعتذر، لكن واجهت خطأ في ترجمة الرد. إليك الرد باللغة الإنجليزية:",
    "de": "Es tut mir leid, aber beim Übersetzen der Antwort ist ein Fehler aufgetreten. Hier ist die Antwort auf Englisch:",
}


class TranslationResult(BaseModel):
    """Result of translation operation."""

    original_text: str = Field(description="Original text before translation")
    translated_text: str = Field(description="Translated text")
    source_language: str = Field(description="Source language code")
    target_language: str = Field(description="Target language code")
    success: bool = Field(description="Whether translation was successful")
    error: Optional[str] = Field(default=None, description="Error message if translation failed")
    translation_time_ms: float = Field(description="Time taken for translation in milliseconds")
    service_used: str = Field(description="Translation service used")


class TranslationService:
    """Translation service for multi-language support."""

    def __init__(self, service_type: str = TRANSLATION_SERVICE_GOOGLE):
        """
        Initialize translation service.

        Args:
            service_type: Type of translation service (google, deepl, nllb)
        """
        self.logger = logger
        self.service_type = service_type
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the translation service client."""
        try:
            # Placeholder for actual service initialization
            # In production, this would initialize Google Translate, DeepL, or NLLB
            logger.info(f"Translation service initialized: {self.service_type} (placeholder mode)")
            self.client = "placeholder"
        except Exception as e:
            logger.error(f"Failed to initialize translation service: {e}")
            self.client = None

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """
        Translate text from source to target language.

        Args:
            text: Text to translate
            source_language: Source language code (e.g., 'en', 'hi')
            target_language: Target language code (e.g., 'en', 'hi')

        Returns:
            Translation result
        """
        start_time = time.time()

        # Skip translation if source and target are the same
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                success=True,
                translation_time_ms=0.0,
                service_used=self.service_type,
            )

        try:
            # Perform translation
            translated_text = self._translate_internal(text, source_language, target_language)

            translation_time_ms = (time.time() - start_time) * 1000

            result = TranslationResult(
                original_text=text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
                success=True,
                translation_time_ms=translation_time_ms,
                service_used=self.service_type,
            )

            logger.info(
                f"Translation successful: {source_language} -> {target_language}, "
                f"time: {translation_time_ms:.2f}ms"
            )

            return result

        except Exception as e:
            translation_time_ms = (time.time() - start_time) * 1000

            result = TranslationResult(
                original_text=text,
                translated_text=text,  # Return original on failure
                source_language=source_language,
                target_language=target_language,
                success=False,
                error=str(e),
                translation_time_ms=translation_time_ms,
                service_used=self.service_type,
            )

            logger.error(f"Translation failed: {e}")

            return result

    def _translate_internal(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """
        Internal translation logic.

        Args:
            text: Text to translate
            source_language: Source language code
            target_language: Target language code

        Returns:
            Translated text

        Raises:
            Exception: If translation fails
        """
        # Placeholder translation logic
        # In production, this would use actual Google Translate, DeepL, or NLLB
        if not text or len(text.strip()) == 0:
            return text

        # For placeholder, we'll just return the text with a prefix
        # In production, replace with actual translation API call
        translated = f"[Translated from {source_language} to {target_language}] {text}"

        # Simulate translation delay
        time.sleep(0.01)

        return translated

    def translate_to_english(
        self,
        text: str,
        source_language: str,
    ) -> TranslationResult:
        """
        Translate text to English for AI processing.

        Args:
            text: Text to translate
            source_language: Source language code

        Returns:
            Translation result
        """
        return self.translate(text, source_language, TARGET_LANGUAGE)

    def translate_from_english(
        self,
        text: str,
        target_language: str,
    ) -> TranslationResult:
        """
        Translate text from English to customer's language.

        Args:
            text: Text to translate
            target_language: Target language code

        Returns:
            Translation result
        """
        return self.translate(text, TARGET_LANGUAGE, target_language)

    def get_apology_message(self, language_code: str) -> str:
        """
        Get apology message for translation failure.

        Args:
            language_code: Language code for apology

        Returns:
            Apology message in the specified language
        """
        return TRANSLATION_FAILURE_APOLOGY.get(language_code, TRANSLATION_FAILURE_APOLOGY["en"])

    def handle_translation_failure(
        self,
        original_response: str,
        customer_language: str,
    ) -> str:
        """
        Handle translation failure by returning English response with apology.

        Args:
            original_response: Original English response
            customer_language: Customer's language code

        Returns:
            Response with apology in customer's language + English response
        """
        apology = self.get_apology_message(customer_language)
        return f"{apology}\n\n{original_response}"
