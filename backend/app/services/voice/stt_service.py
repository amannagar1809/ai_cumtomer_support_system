"""Speech-to-Text service for voice bot functionality."""

import base64
import io
import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# STT providers
STT_PROVIDER_WHISPER = "whisper"
STT_PROVIDER_DEEPGRAM = "deepgram"
STT_PROVIDER_GOOGLE = "google"

# Supported audio formats
SUPPORTED_FORMATS = ["mp3", "wav", "ogg", "m4a"]

# Maximum audio duration in seconds
MAX_AUDIO_DURATION = 60

# Confidence threshold for transcription
CONFIDENCE_THRESHOLD = 0.7

# Fallback message for low confidence
FALLBACK_MESSAGE = "Could you repeat that?"

# Maximum latency target in milliseconds
MAX_LATENCY_TARGET_MS = 500

# Chunk size for chunked processing (in seconds)
CHUNK_DURATION_SECONDS = 2

# Common phrases cache TTL in seconds
PHRASE_CACHE_TTL = 3600

# Regional endpoints
REGIONAL_ENDPOINTS = {
    "us-east": "https://stt.api.us-east.example.com",
    "us-west": "https://stt.api.us-west.example.com",
    "eu-west": "https://stt.api.eu-west.example.com",
    "asia-east": "https://stt.api.asia-east.example.com",
    "asia-south": "https://stt.api.asia-south.example.com",
}


class STTProvider(str, Enum):
    """Supported STT providers."""

    whisper = STT_PROVIDER_WHISPER
    deepgram = STT_PROVIDER_DEEPGRAM
    google = STT_PROVIDER_GOOGLE


class TranscriptionResult(BaseModel):
    """Result of speech-to-text transcription."""

    text: str = Field(description="Transcribed text")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    duration: float = Field(description="Audio duration in seconds")
    language: Optional[str] = Field(default=None, description="Detected language")
    speakers: Optional[int] = Field(default=None, description="Number of speakers detected")
    provider: str = Field(description="STT provider used")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    is_streaming: bool = Field(default=False, description="Whether streaming was used")
    noise_reduced: bool = Field(default=False, description="Whether noise reduction was applied")
    is_chunked: bool = Field(default=False, description="Whether chunked processing was used")
    from_cache: bool = Field(default=False, description="Whether result came from phrase cache")
    regional_endpoint: Optional[str] = Field(default=None, description="Regional endpoint used")
    latency_target_met: bool = Field(default=False, description="Whether latency target was met")


class STTService:
    """Speech-to-Text service with provider abstraction and latency optimization."""

    def __init__(self, provider: STTProvider = STTProvider.whisper, user_region: Optional[str] = None):
        """
        Initialize STT service.

        Args:
            provider: STT provider to use (whisper, deepgram, google)
            user_region: User's region for regional endpoint selection
        """
        self.logger = logger
        self.provider = provider
        self.user_region = user_region
        self.phrase_cache = defaultdict(dict)  # Cache for common phrases
        self.phrase_cache_timestamps = defaultdict(dict)  # Cache timestamps
        self._initialize_provider()
        self._select_regional_endpoint()

    def _initialize_provider(self):
        """Initialize the STT provider client."""
        try:
            # Placeholder for actual provider initialization
            # In production, this would initialize Whisper, Deepgram, or Google STT
            logger.info(f"STT provider initialized: {self.provider.value} (placeholder mode)")
            self.client = "placeholder"
        except Exception as e:
            logger.error(f"Failed to initialize STT provider: {e}")
            self.client = None

    def _select_regional_endpoint(self):
        """Select regional endpoint closest to user."""
        if self.user_region and self.user_region in REGIONAL_ENDPOINTS:
            self.regional_endpoint = REGIONAL_ENDPOINTS[self.user_region]
            logger.info(f"Using regional endpoint: {self.user_region} -> {self.regional_endpoint}")
        else:
            self.regional_endpoint = REGIONAL_ENDPOINTS.get("us-east")
            logger.info(f"Using default regional endpoint: {self.regional_endpoint}")

    def transcribe(
        self,
        audio_data: bytes,
        audio_format: str,
        use_streaming: bool = False,
        apply_noise_reduction: bool = True,
        detect_speakers: bool = False,
        use_chunked: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text with latency optimization.

        Args:
            audio_data: Audio data as bytes
            audio_format: Audio format (mp3, wav, ogg, m4a)
            use_streaming: Whether to use streaming transcription
            apply_noise_reduction: Whether to apply noise reduction
            detect_speakers: Whether to detect multiple speakers
            use_chunked: Whether to use chunked processing

        Returns:
            Transcription result
        """
        start_time = time.time()

        # Validate audio format
        if audio_format.lower() not in SUPPORTED_FORMATS:
            return TranscriptionResult(
                text=FALLBACK_MESSAGE,
                confidence=0.0,
                duration=0.0,
                provider=self.provider.value,
                processing_time_ms=0.0,
                regional_endpoint=self.regional_endpoint,
            )

        try:
            # Apply noise reduction if requested
            processed_audio = audio_data
            if apply_noise_reduction:
                processed_audio = self._apply_noise_reduction(audio_data)

            # Get audio duration (placeholder)
            duration = self._get_audio_duration(audio_data)

            # Check duration limit
            if duration > MAX_AUDIO_DURATION:
                logger.warning(f"Audio duration {duration}s exceeds limit {MAX_AUDIO_DURATION}s")
                return TranscriptionResult(
                    text=FALLBACK_MESSAGE,
                    confidence=0.0,
                    duration=duration,
                    provider=self.provider.value,
                    processing_time_ms=0.0,
                    regional_endpoint=self.regional_endpoint,
                )

            # Check phrase cache first for faster recognition
            cached_result = self._check_phrase_cache(processed_audio)
            if cached_result:
                processing_time_ms = (time.time() - start_time) * 1000
                cached_result.processing_time_ms = processing_time_ms
                cached_result.from_cache = True
                cached_result.regional_endpoint = self.regional_endpoint
                cached_result.latency_target_met = processing_time_ms <= MAX_LATENCY_TARGET_MS
                logger.info(f"Transcription from cache: {cached_result.text[:50]}..., time: {processing_time_ms:.2f}ms")
                return cached_result

            # Perform transcription with chunked processing if enabled
            if use_chunked and duration > CHUNK_DURATION_SECONDS:
                transcription = self._transcribe_chunked(processed_audio, audio_format)
            elif use_streaming and duration > 10:
                # Use streaming for longer audio
                transcription = self._transcribe_streaming(processed_audio, audio_format)
            else:
                # Use regular transcription
                transcription = self._transcribe_regular(processed_audio, audio_format)

            # Detect speakers if requested
            speakers = None
            if detect_speakers:
                speakers = self._detect_speakers(processed_audio)

            processing_time_ms = (time.time() - start_time) * 1000

            # Cache the result for common phrases
            self._cache_phrase(processed_audio, transcription)

            result = TranscriptionResult(
                text=transcription["text"],
                confidence=transcription["confidence"],
                duration=duration,
                language=transcription.get("language"),
                speakers=speakers,
                provider=self.provider.value,
                processing_time_ms=processing_time_ms,
                is_streaming=use_streaming and duration > 10,
                noise_reduced=apply_noise_reduction,
                is_chunked=use_chunked and duration > CHUNK_DURATION_SECONDS,
                from_cache=False,
                regional_endpoint=self.regional_endpoint,
                latency_target_met=processing_time_ms <= MAX_LATENCY_TARGET_MS,
            )

            logger.info(
                f"Transcription completed: {len(result.text)} chars, "
                f"confidence: {result.confidence:.2f}, "
                f"duration: {result.duration:.2f}s, "
                f"time: {result.processing_time_ms:.2f}ms, "
                f"target_met: {result.latency_target_met}, "
                f"chunked: {result.is_chunked}"
            )

            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000

            result = TranscriptionResult(
                text=FALLBACK_MESSAGE,
                confidence=0.0,
                duration=0.0,
                provider=self.provider.value,
                processing_time_ms=processing_time_ms,
                regional_endpoint=self.regional_endpoint,
                latency_target_met=False,
            )

            logger.error(f"Transcription failed: {e}")

            return result

    def _transcribe_regular(self, audio_data: bytes, audio_format: str) -> dict:
        """
        Perform regular transcription.

        Args:
            audio_data: Audio data
            audio_format: Audio format

        Returns:
            Transcription dict with text and confidence
        """
        # Placeholder implementation
        # In production, this would call Whisper API, Deepgram, or Google STT
        # For now, return a placeholder transcription
        return {
            "text": "This is a placeholder transcription from the audio file.",
            "confidence": 0.85,
            "language": "en",
        }

    def _transcribe_chunked(self, audio_data: bytes, audio_format: str) -> dict:
        """
        Perform chunked transcription for low latency (send while user speaks).

        Args:
            audio_data: Audio data
            audio_format: Audio format

        Returns:
            Transcription dict with text and confidence
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Split audio into chunks (CHUNK_DURATION_SECONDS)
        # 2. Send chunks for transcription as they're available
        # 3. Merge partial results for final transcription
        # For now, return a placeholder transcription
        return {
            "text": "This is a placeholder chunked transcription from the audio file.",
            "confidence": 0.82,
            "language": "en",
        }

    def _transcribe_streaming(self, audio_data: bytes, audio_format: str) -> dict:
        """
        Perform streaming transcription for long audio.

        Args:
            audio_data: Audio data
            audio_format: Audio format

        Returns:
            Transcription dict with text and confidence
        """
        # Placeholder implementation
        # In production, this would use streaming API from the provider
        # For now, return a placeholder transcription
        return {
            "text": "This is a placeholder streaming transcription from the audio file.",
            "confidence": 0.80,
            "language": "en",
        }

    def _check_phrase_cache(self, audio_data: bytes) -> Optional[TranscriptionResult]:
        """
        Check if audio matches a cached common phrase.

        Args:
            audio_data: Audio data

        Returns:
            Cached transcription result or None
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Generate audio fingerprint/hash
        # 2. Check against phrase cache
        # 3. Return cached result if match found
        # For now, return None (no cache hit)
        return None

    def _cache_phrase(self, audio_data: bytes, transcription: dict):
        """
        Cache transcription result for common phrases.

        Args:
            audio_data: Audio data
            transcription: Transcription result
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Generate audio fingerprint/hash
        # 2. Store in phrase cache with timestamp
        # 3. Clean up expired cache entries
        pass

    def transcribe_parallel(
        self,
        audio_data: bytes,
        audio_format: str,
        languages: list[str],
    ) -> dict[str, TranscriptionResult]:
        """
        Transcribe audio in parallel for multiple languages.

        Args:
            audio_data: Audio data
            audio_format: Audio format
            languages: List of language codes to transcribe for

        Returns:
            Dictionary of language codes to transcription results
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Spawn parallel transcription tasks for each language
        # 2. Wait for all to complete
        # 3. Return results for all languages
        # For now, return empty dict
        logger.info(f"Parallel transcription requested for languages: {languages}")
        return {}

    def _apply_noise_reduction(self, audio_data: bytes) -> bytes:
        """
        Apply noise reduction to audio.

        Args:
            audio_data: Audio data

        Returns:
            Processed audio data
        """
        # Placeholder implementation
        # In production, this would use audio processing libraries like librosa, pydub
        # For now, return the original audio
        return audio_data

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
        # For now, return a placeholder duration
        return 5.0

    def _detect_speakers(self, audio_data: bytes) -> Optional[int]:
        """
        Detect number of speakers in audio (diarization).

        Args:
            audio_data: Audio data

        Returns:
            Number of speakers or None
        """
        # Placeholder implementation
        # In production, this would use speaker diarization models
        # For now, return None
        return None

    def transcribe_base64(
        self,
        base64_audio: str,
        audio_format: str,
        use_streaming: bool = False,
        apply_noise_reduction: bool = True,
        detect_speakers: bool = False,
        use_chunked: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe base64-encoded audio to text with latency optimization.

        Args:
            base64_audio: Base64-encoded audio data
            audio_format: Audio format (mp3, wav, ogg, m4a)
            use_streaming: Whether to use streaming transcription
            apply_noise_reduction: Whether to apply noise reduction
            detect_speakers: Whether to detect multiple speakers
            use_chunked: Whether to use chunked processing

        Returns:
            Transcription result
        """
        try:
            # Decode base64
            audio_data = base64.b64decode(base64_audio)
            return self.transcribe(
                audio_data=audio_data,
                audio_format=audio_format,
                use_streaming=use_streaming,
                apply_noise_reduction=apply_noise_reduction,
                detect_speakers=detect_speakers,
                use_chunked=use_chunked,
            )
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            return TranscriptionResult(
                text=FALLBACK_MESSAGE,
                confidence=0.0,
                duration=0.0,
                provider=self.provider.value,
                processing_time_ms=0.0,
                regional_endpoint=self.regional_endpoint,
                latency_target_met=False,
            )

    def should_use_fallback(self, confidence: float) -> bool:
        """
        Determine if fallback message should be used based on confidence.

        Args:
            confidence: Confidence score

        Returns:
            True if fallback should be used
        """
        return confidence < CONFIDENCE_THRESHOLD
