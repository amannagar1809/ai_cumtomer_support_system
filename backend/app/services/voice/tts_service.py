"""Text-to-Speech service for voice bot functionality."""

import base64
import hashlib
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# TTS providers
TTS_PROVIDER_ELEVENLABS = "elevenlabs"
TTS_PROVIDER_AZURE = "azure"
TTS_PROVIDER_AMAZON = "amazon"

# Audio format for streaming
AUDIO_FORMAT_MP3 = "mp3"
CHUNK_SIZE_BYTES = 8192  # 8KB chunks for streaming

# Response cache TTL in seconds
RESPONSE_CACHE_TTL = 3600

# Voice styles
VOICE_STYLE_CASUAL = "casual"
VOICE_STYLE_PROFESSIONAL = "professional"
VOICE_STYLES = [VOICE_STYLE_CASUAL, VOICE_STYLE_PROFESSIONAL]

# Voice genders
VOICE_GENDER_MALE = "male"
VOICE_GENDER_FEMALE = "female"
VOICE_GENDERS = [VOICE_GENDER_MALE, VOICE_GENDER_FEMALE]


class TTSProvider(str, Enum):
    """Supported TTS providers."""

    elevenlabs = TTS_PROVIDER_ELEVENLABS
    azure = TTS_PROVIDER_AZURE
    amazon = TTS_PROVIDER_AMAZON


class VoiceConfig(BaseModel):
    """Voice configuration."""

    voice_id: str = Field(description="Voice ID from provider")
    name: str = Field(description="Voice name")
    language: str = Field(description="Language code (e.g., 'en', 'hi')")
    gender: str = Field(description="Gender (male/female)")
    style: str = Field(description="Style (casual/professional)")


class TTSResult(BaseModel):
    """Result of text-to-speech conversion."""

    audio_data: bytes = Field(description="Generated audio data")
    audio_format: str = Field(description="Audio format (mp3)")
    duration: float = Field(description="Audio duration in seconds")
    voice_id: str = Field(description="Voice ID used")
    provider: str = Field(description="TTS provider used")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    is_streamed: bool = Field(default=False, description="Whether streaming was used")
    from_cache: bool = Field(default=False, description="Whether result came from cache")
    used_ssml: bool = Field(default=False, description="Whether SSML was used")


# Voice catalog for different languages and providers
VOICE_CATALOG = {
    "elevenlabs": {
        "en": {
            "male": {
                "casual": VoiceConfig(
                    voice_id="eleven_male_en_casual",
                    name="Casual Male (English)",
                    language="en",
                    gender="male",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="eleven_male_en_professional",
                    name="Professional Male (English)",
                    language="en",
                    gender="male",
                    style="professional",
                ),
            },
            "female": {
                "casual": VoiceConfig(
                    voice_id="eleven_female_en_casual",
                    name="Casual Female (English)",
                    language="en",
                    gender="female",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="eleven_female_en_professional",
                    name="Professional Female (English)",
                    language="en",
                    gender="female",
                    style="professional",
                ),
            },
        },
        "hi": {
            "male": {
                "casual": VoiceConfig(
                    voice_id="eleven_male_hi_casual",
                    name="Casual Male (Hindi)",
                    language="hi",
                    gender="male",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="eleven_male_hi_professional",
                    name="Professional Male (Hindi)",
                    language="hi",
                    gender="male",
                    style="professional",
                ),
            },
            "female": {
                "casual": VoiceConfig(
                    voice_id="eleven_female_hi_casual",
                    name="Casual Female (Hindi)",
                    language="hi",
                    gender="female",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="eleven_female_hi_professional",
                    name="Professional Female (Hindi)",
                    language="hi",
                    gender="female",
                    style="professional",
                ),
            },
        },
    },
    "azure": {
        "en": {
            "male": {
                "casual": VoiceConfig(
                    voice_id="azure_male_en_casual",
                    name="Casual Male (English)",
                    language="en",
                    gender="male",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="azure_male_en_professional",
                    name="Professional Male (English)",
                    language="en",
                    gender="male",
                    style="professional",
                ),
            },
            "female": {
                "casual": VoiceConfig(
                    voice_id="azure_female_en_casual",
                    name="Casual Female (English)",
                    language="en",
                    gender="female",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="azure_female_en_professional",
                    name="Professional Female (English)",
                    language="en",
                    gender="female",
                    style="professional",
                ),
            },
        },
    },
    "amazon": {
        "en": {
            "male": {
                "casual": VoiceConfig(
                    voice_id="amazon_male_en_casual",
                    name="Casual Male (English)",
                    language="en",
                    gender="male",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="amazon_male_en_professional",
                    name="Professional Male (English)",
                    language="en",
                    gender="male",
                    style="professional",
                ),
            },
            "female": {
                "casual": VoiceConfig(
                    voice_id="amazon_female_en_casual",
                    name="Casual Female (English)",
                    language="en",
                    gender="female",
                    style="casual",
                ),
                "professional": VoiceConfig(
                    voice_id="amazon_female_en_professional",
                    name="Professional Female (English)",
                    language="en",
                    gender="female",
                    style="professional",
                ),
            },
        },
    },
}


class TTSService:
    """Text-to-Speech service with provider abstraction."""

    def __init__(
        self,
        provider: TTSProvider = TTSProvider.elevenlabs,
        default_voice_id: Optional[str] = None,
    ):
        """
        Initialize TTS service.

        Args:
            provider: TTS provider to use (elevenlabs, azure, amazon)
            default_voice_id: Default voice ID to use
        """
        self.logger = logger
        self.provider = provider
        self.default_voice_id = default_voice_id
        self.response_cache = defaultdict(dict)  # Cache for common responses
        self.response_cache_timestamps = defaultdict(dict)  # Cache timestamps
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the TTS provider client."""
        try:
            # Placeholder for actual provider initialization
            # In production, this would initialize ElevenLabs, Azure TTS, or Amazon Polly
            logger.info(f"TTS provider initialized: {self.provider.value} (placeholder mode)")
            self.client = "placeholder"
        except Exception as e:
            logger.error(f"Failed to initialize TTS provider: {e}")
            self.client = None

    def get_available_voices(
        self,
        language: str,
        provider: Optional[str] = None,
    ) -> list[VoiceConfig]:
        """
        Get available voices for a language.

        Args:
            language: Language code (e.g., 'en', 'hi')
            provider: Provider name (uses default if not specified)

        Returns:
            List of available voice configurations
        """
        provider_name = provider or self.provider.value
        voices = []

        if provider_name in VOICE_CATALOG and language in VOICE_CATALOG[provider_name]:
            for gender, gender_voices in VOICE_CATALOG[provider_name][language].items():
                for style, voice_config in gender_voices.items():
                    voices.append(voice_config)

        return voices

    def get_voice(
        self,
        language: str,
        gender: str = "female",
        style: str = "casual",
        provider: Optional[str] = None,
    ) -> Optional[VoiceConfig]:
        """
        Get a specific voice configuration.

        Args:
            language: Language code (e.g., 'en', 'hi')
            gender: Gender (male/female)
            style: Style (casual/professional)
            provider: Provider name (uses default if not specified)

        Returns:
            Voice configuration or None if not found
        """
        provider_name = provider or self.provider.value

        if (
            provider_name in VOICE_CATALOG
            and language in VOICE_CATALOG[provider_name]
            and gender in VOICE_CATALOG[provider_name][language]
            and style in VOICE_CATALOG[provider_name][language][gender]
        ):
            return VOICE_CATALOG[provider_name][language][gender][style]

        return None

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
        use_ssml: bool = False,
        use_streaming: bool = False,
    ) -> TTSResult:
        """
        Synthesize text to audio.

        Args:
            text: Text to synthesize
            voice_id: Voice ID to use (uses default if not specified)
            language: Language code
            use_ssml: Whether to use SSML for natural pauses and emphasis
            use_streaming: Whether to use streaming

        Returns:
            TTS result with audio data
        """
        start_time = time.time()

        # Use default voice if not specified
        if not voice_id:
            voice_id = self.default_voice_id

        # Check response cache first
        cache_key = self._generate_cache_key(text, voice_id, language, use_ssml)
        cached_result = self._check_response_cache(cache_key)
        if cached_result:
            processing_time_ms = (time.time() - start_time) * 1000
            cached_result.processing_time_ms = processing_time_ms
            cached_result.from_cache = True
            logger.info(f"TTS from cache: {text[:50]}..., time: {processing_time_ms:.2f}ms")
            return cached_result

        try:
            # Convert to SSML if requested
            text_to_speak = text
            if use_ssml:
                text_to_speak = self._convert_to_ssml(text, language)

            # Generate audio
            audio_data = self._generate_audio(text_to_speak, voice_id, language)

            # Get audio duration (placeholder)
            duration = self._get_audio_duration(audio_data)

            processing_time_ms = (time.time() - start_time) * 1000

            # Cache the result
            result = TTSResult(
                audio_data=audio_data,
                audio_format=AUDIO_FORMAT_MP3,
                duration=duration,
                voice_id=voice_id or "default",
                provider=self.provider.value,
                processing_time_ms=processing_time_ms,
                is_streamed=use_streaming,
                from_cache=False,
                used_ssml=use_ssml,
            )
            self._cache_response(cache_key, result)

            logger.info(
                f"TTS completed: {len(text)} chars, "
                f"duration: {result.duration:.2f}s, "
                f"time: {result.processing_time_ms:.2f}ms, "
                f"voice: {result.voice_id}"
            )

            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000

            logger.error(f"TTS failed: {e}")

            # Return empty result on failure
            return TTSResult(
                audio_data=b"",
                audio_format=AUDIO_FORMAT_MP3,
                duration=0.0,
                voice_id=voice_id or "default",
                provider=self.provider.value,
                processing_time_ms=processing_time_ms,
                is_streamed=use_streaming,
                from_cache=False,
                used_ssml=use_ssml,
            )

    def _generate_audio(self, text: str, voice_id: str, language: str) -> bytes:
        """
        Generate audio from text using provider.

        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            language: Language code

        Returns:
            Audio data as bytes
        """
        # Placeholder implementation
        # In production, this would call ElevenLabs, Azure TTS, or Amazon Polly
        # For now, return placeholder audio data
        return b"placeholder_audio_data"

    def _convert_to_ssml(self, text: str, language: str) -> str:
        """
        Convert plain text to SSML for natural pauses and emphasis.

        Args:
            text: Plain text
            language: Language code

        Returns:
            SSML-formatted text
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Add natural pauses at punctuation
        # 2. Add emphasis for important words
        # 3. Add prosody for natural speech
        # For now, return the text wrapped in SSML tags
        return f'<speak version="1.0" xml:lang="{language}">{text}</speak>'

    def _get_audio_duration(self, audio_data: bytes) -> float:
        """
        Get audio duration in seconds.

        Args:
            audio_data: Audio data

        Returns:
            Duration in seconds
        """
        # Placeholder implementation
        # In production, this would use audio processing libraries
        # For now, return a placeholder duration based on text length
        return 5.0

    def _generate_cache_key(
        self,
        text: str,
        voice_id: str,
        language: str,
        use_ssml: bool,
    ) -> str:
        """
        Generate cache key for response.

        Args:
            text: Text content
            voice_id: Voice ID
            language: Language code
            use_ssml: Whether SSML was used

        Returns:
            Cache key
        """
        key_string = f"{text}:{voice_id}:{language}:{use_ssml}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _check_response_cache(self, cache_key: str) -> Optional[TTSResult]:
        """
        Check if response is in cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None
        """
        # Placeholder implementation
        # In production, this would check cache and validate TTL
        return None

    def _cache_response(self, cache_key: str, result: TTSResult):
        """
        Cache response for future use.

        Args:
            cache_key: Cache key
            result: TTS result to cache
        """
        # Placeholder implementation
        # In production, this would store result with timestamp
        pass

    def stream_audio(self, audio_data: bytes, chunk_size: int = CHUNK_SIZE_BYTES):
        """
        Stream audio data in chunks.

        Args:
            audio_data: Audio data to stream
            chunk_size: Size of each chunk in bytes

        Yields:
            Audio chunks
        """
        for i in range(0, len(audio_data), chunk_size):
            yield audio_data[i : i + chunk_size]

    def synthesize_to_base64(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
        use_ssml: bool = False,
    ) -> str:
        """
        Synthesize text to base64-encoded audio.

        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            language: Language code
            use_ssml: Whether to use SSML

        Returns:
            Base64-encoded audio data
        """
        result = self.synthesize(
            text=text,
            voice_id=voice_id,
            language=language,
            use_ssml=use_ssml,
        )
        return base64.b64encode(result.audio_data).decode("utf-8")
