"""Voice bot schemas."""

from pydantic import BaseModel, Field


class TranscribeAudioRequest(BaseModel):
    """Request to transcribe audio."""

    audio_data: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(..., description="Audio format (mp3, wav, ogg, m4a)")
    use_streaming: bool = Field(default=False, description="Whether to use streaming transcription")
    apply_noise_reduction: bool = Field(default=True, description="Whether to apply noise reduction")
    detect_speakers: bool = Field(default=False, description="Whether to detect multiple speakers")


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
    is_fallback: bool = Field(..., description="Whether fallback message was used")


class UploadAudioResponse(BaseModel):
    """Response for audio upload."""

    transcription_id: str = Field(..., description="Transcription ID")
    status: str = Field(..., description="Status (processing, completed, failed)")
