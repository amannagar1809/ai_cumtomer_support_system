"""Voice bot schemas."""

from pydantic import BaseModel, Field


class TranscribeAudioRequest(BaseModel):
    """Request to transcribe audio."""

    audio_data: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(..., description="Audio format (mp3, wav, ogg, m4a)")
    use_streaming: bool = Field(default=False, description="Whether to use streaming transcription")
    apply_noise_reduction: bool = Field(default=True, description="Whether to apply noise reduction")
    detect_speakers: bool = Field(default=False, description="Whether to detect multiple speakers")
    use_chunked: bool = Field(default=True, description="Whether to use chunked processing for low latency")
    user_region: str | None = Field(default=None, description="User's region for regional endpoint selection")


class TranscribeAudioResponse(BaseModel):
    """Response with transcription result."""

    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0)")
    duration: float = Field(..., description="Audio duration in seconds")
    language: str | None = Field(default=None, description="Detected language")
    speakers: int | None = Field(default=None, description="Number of speakers detected")
    provider: str = Field(..., description="STT provider used")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    is_streaming: bool = Field(..., description="Whether streaming was used")
    noise_reduced: bool = Field(..., description="Whether noise reduction was applied")
    is_chunked: bool = Field(..., description="Whether chunked processing was used")
    from_cache: bool = Field(..., description="Whether result came from phrase cache")
    regional_endpoint: str | None = Field(default=None, description="Regional endpoint used")
    latency_target_met: bool = Field(..., description="Whether 500ms latency target was met")
    is_fallback: bool = Field(..., description="Whether fallback message was used")


class UploadAudioResponse(BaseModel):
    """Response for audio upload."""

    transcription_id: str = Field(..., description="Transcription ID")
    status: str = Field(..., description="Status (processing, completed, failed)")


class VoiceConfig(BaseModel):
    """Voice configuration."""

    voice_id: str = Field(..., description="Voice ID from provider")
    name: str = Field(..., description="Voice name")
    language: str = Field(..., description="Language code (e.g., 'en', 'hi')")
    gender: str = Field(..., description="Gender (male/female)")
    style: str = Field(..., description="Style (casual/professional)")


class SynthesizeRequest(BaseModel):
    """Request to synthesize text to speech."""

    text: str = Field(..., description="Text to synthesize")
    voice_id: str | None = Field(default=None, description="Voice ID to use")
    language: str = Field(default="en", description="Language code")
    use_ssml: bool = Field(default=False, description="Whether to use SSML for natural pauses")
    use_streaming: bool = Field(default=False, description="Whether to use streaming")


class SynthesizeResponse(BaseModel):
    """Response with synthesized audio."""

    audio_data: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(..., description="Audio format (mp3)")
    duration: float = Field(..., description="Audio duration in seconds")
    voice_id: str = Field(..., description="Voice ID used")
    provider: str = Field(..., description="TTS provider used")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    is_streamed: bool = Field(..., description="Whether streaming was used")
    from_cache: bool = Field(..., description="Whether result came from cache")
    used_ssml: bool = Field(..., description="Whether SSML was used")


class SetVoicePreferenceRequest(BaseModel):
    """Request to set user's voice preference."""

    user_id: str = Field(..., description="User ID")
    voice_id: str = Field(..., description="Voice ID")
    gender: str = Field(..., description="Gender (male/female)")
    style: str = Field(..., description="Style (casual/professional)")


class VoicePreferenceResponse(BaseModel):
    """Response with user's voice preference."""

    user_id: str = Field(..., description="User ID")
    voice_id: str | None = Field(..., description="Preferred voice ID")
    gender: str | None = Field(..., description="Preferred gender")
    style: str | None = Field(..., description="Preferred style")


class AvailableVoicesResponse(BaseModel):
    """Response with available voices."""

    voices: list[VoiceConfig] = Field(..., description="List of available voices")


class VoiceFlowRequest(BaseModel):
    """Request for voice flow (STT → LangGraph → TTS)."""

    audio_data: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(..., description="Audio format (mp3, wav, ogg, m4a)")
    conversation_id: str | None = Field(default=None, description="Conversation ID")
    user_id: str | None = Field(default=None, description="User ID")
    channel: str = Field(default="voice", description="Communication channel")


class VoiceFlowResponse(BaseModel):
    """Response from voice flow with audio output."""

    transcription: str = Field(..., description="Transcribed text from audio input")
    transcription_confidence: float = Field(..., description="Transcription confidence score")
    text_response: str = Field(..., description="AI text response")
    audio_output: str = Field(..., description="Base64-encoded audio output")
    audio_format: str = Field(..., description="Audio output format (mp3)")
    audio_duration: float = Field(..., description="Audio output duration in seconds")
    voice_id: str | None = Field(default=None, description="Voice ID used for TTS")
    stt_provider: str = Field(..., description="STT provider used")
    tts_provider: str = Field(..., description="TTS provider used")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")

