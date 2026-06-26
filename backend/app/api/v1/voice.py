"""Voice bot API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.voice import (
    TranscribeAudioRequest,
    TranscribeAudioResponse,
    UploadAudioResponse,
)
from app.services.voice.stt_service import STTService, STTProvider

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/transcribe",
    response_model=TranscribeAudioResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe audio to text",
)
async def transcribe_audio(
    body: TranscribeAudioRequest,
    db: AsyncSession = Depends(get_db),
) -> TranscribeAudioResponse:
    """
    Transcribe base64-encoded audio to text.

    Args:
        body: Transcription request with base64 audio
        db: Database session

    Returns:
        Transcription result with confidence score
    """
    try:
        # Initialize STT service (using Whisper as default)
        stt_service = STTService(provider=STTProvider.whisper)

        # Transcribe audio
        result = stt_service.transcribe_base64(
            base64_audio=body.audio_data,
            audio_format=body.audio_format,
            use_streaming=body.use_streaming,
            apply_noise_reduction=body.apply_noise_reduction,
            detect_speakers=body.detect_speakers,
        )

        # Check if fallback should be used
        is_fallback = stt_service.should_use_fallback(result.confidence)
        if is_fallback:
            result.text = "Could you repeat that?"

        return TranscribeAudioResponse(
            text=result.text,
            confidence=result.confidence,
            duration=result.duration,
            language=result.language,
            speakers=result.speakers,
            provider=result.provider,
            processing_time_ms=result.processing_time_ms,
            is_streaming=result.is_streaming,
            noise_reduced=result.noise_reduced,
            is_fallback=is_fallback,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.post(
    "/upload",
    response_model=UploadAudioResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload audio file for transcription",
)
async def upload_audio(
    file: UploadFile = File(..., description="Audio file (mp3, wav, ogg, m4a)"),
    use_streaming: bool = Form(default=False, description="Whether to use streaming transcription"),
    apply_noise_reduction: bool = Form(default=True, description="Whether to apply noise reduction"),
    detect_speakers: bool = Form(default=False, description="Whether to detect multiple speakers"),
    db: AsyncSession = Depends(get_db),
) -> UploadAudioResponse:
    """
    Upload audio file for transcription.

    Args:
        file: Audio file
        use_streaming: Whether to use streaming transcription
        apply_noise_reduction: Whether to apply noise reduction
        detect_speakers: Whether to detect multiple speakers
        db: Database session

    Returns:
        Transcription ID for tracking
    """
    try:
        # Validate file format
        file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
        if file_extension not in ["mp3", "wav", "ogg", "m4a"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: {file_extension}. Supported formats: mp3, wav, ogg, m4a",
            )

        # Read file content
        audio_data = await file.read()

        # Generate transcription ID
        transcription_id = str(uuid.uuid4())

        # In production, this would:
        # 1. Store audio file in S3 or similar
        # 2. Queue transcription job
        # 3. Return ID for status checking

        # For now, process synchronously (placeholder)
        stt_service = STTService(provider=STTProvider.whisper)
        result = stt_service.transcribe(
            audio_data=audio_data,
            audio_format=file_extension,
            use_streaming=use_streaming,
            apply_noise_reduction=apply_noise_reduction,
            detect_speakers=detect_speakers,
        )

        # Log transcription result
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Transcription {transcription_id}: {result.text[:50]}..., "
            f"confidence: {result.confidence:.2f}"
        )

        return UploadAudioResponse(
            transcription_id=transcription_id,
            status="completed",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio upload failed: {str(e)}",
        )


@router.get(
    "/transcription/{transcription_id}",
    response_model=TranscribeAudioResponse,
    summary="Get transcription result",
)
async def get_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(get_db),
) -> TranscribeAudioResponse:
    """
    Get transcription result by ID.

    Args:
        transcription_id: Transcription ID
        db: Database session

    Returns:
        Transcription result
    """
    # Placeholder implementation
    # In production, this would:
    # 1. Look up transcription by ID in database
    # 2. Return the result if completed
    # 3. Return status if still processing

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Transcription lookup not yet implemented",
    )
