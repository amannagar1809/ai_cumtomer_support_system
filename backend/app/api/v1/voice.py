"""Voice bot API endpoints."""

import base64
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.voice import (
    AvailableVoicesResponse,
    SetVoicePreferenceRequest,
    SynthesizeRequest,
    SynthesizeResponse,
    TranscribeAudioRequest,
    TranscribeAudioResponse,
    UploadAudioResponse,
    VoiceConfig,
    VoiceFlowRequest,
    VoiceFlowResponse,
    VoicePreferenceResponse,
)
from app.services.voice.stt_service import STTService, STTProvider
from app.services.voice.tts_service import TTSService, TTSProvider

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/transcribe",
    response_model=TranscribeAudioResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe audio to text with latency optimization",
)
async def transcribe_audio(
    body: TranscribeAudioRequest,
    db: AsyncSession = Depends(get_db),
) -> TranscribeAudioResponse:
    """
    Transcribe base64-encoded audio to text with latency optimization.

    Args:
        body: Transcription request with base64 audio and optimization options
        db: Database session

    Returns:
        Transcription result with confidence score and latency metrics
    """
    try:
        # Initialize STT service with regional endpoint selection
        stt_service = STTService(
            provider=STTProvider.whisper,
            user_region=body.user_region,
        )

        # Transcribe audio with latency optimizations
        result = stt_service.transcribe_base64(
            base64_audio=body.audio_data,
            audio_format=body.audio_format,
            use_streaming=body.use_streaming,
            apply_noise_reduction=body.apply_noise_reduction,
            detect_speakers=body.detect_speakers,
            use_chunked=body.use_chunked,
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
            is_chunked=result.is_chunked,
            from_cache=result.from_cache,
            regional_endpoint=result.regional_endpoint,
            latency_target_met=result.latency_target_met,
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


@router.post(
    "/synthesize",
    response_model=SynthesizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize text to speech",
)
async def synthesize_speech(
    body: SynthesizeRequest,
    db: AsyncSession = Depends(get_db),
) -> SynthesizeResponse:
    """
    Synthesize text to audio.

    Args:
        body: Synthesis request with text and voice options
        db: Database session

    Returns:
        Synthesized audio with metadata
    """
    try:
        # Initialize TTS service (using ElevenLabs as default)
        tts_service = TTSService(provider=TTSProvider.elevenlabs)

        # Synthesize audio
        result = tts_service.synthesize(
            text=body.text,
            voice_id=body.voice_id,
            language=body.language,
            use_ssml=body.use_ssml,
            use_streaming=body.use_streaming,
        )

        # Convert audio to base64
        audio_base64 = tts_service.synthesize_to_base64(
            text=body.text,
            voice_id=body.voice_id,
            language=body.language,
            use_ssml=body.use_ssml,
        )

        return SynthesizeResponse(
            audio_data=audio_base64,
            audio_format=result.audio_format,
            duration=result.duration,
            voice_id=result.voice_id,
            provider=result.provider,
            processing_time_ms=result.processing_time_ms,
            is_streamed=result.is_streamed,
            from_cache=result.from_cache,
            used_ssml=result.used_ssml,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(e)}",
        )


@router.post(
    "/voice/preference",
    response_model=VoicePreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Set user's voice preference",
)
async def set_voice_preference(
    body: SetVoicePreferenceRequest,
    db: AsyncSession = Depends(get_db),
) -> VoicePreferenceResponse:
    """
    Set user's preferred voice for TTS.

    Args:
        body: Voice preference request
        db: Database session

    Returns:
        Updated voice preference
    """
    try:
        # Update user's voice preference
        result = await db.execute(
            select(User).where(User.id == body.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user.preferred_voice_id = body.voice_id
        user.voice_gender = body.gender
        user.voice_style = body.style

        await db.commit()
        await db.refresh(user)

        return VoicePreferenceResponse(
            user_id=str(user.id),
            voice_id=user.preferred_voice_id,
            gender=user.voice_gender,
            style=user.voice_style,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set voice preference: {str(e)}",
        )


@router.get(
    "/voice/preference/{user_id}",
    response_model=VoicePreferenceResponse,
    summary="Get user's voice preference",
)
async def get_voice_preference(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> VoicePreferenceResponse:
    """
    Get user's preferred voice for TTS.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        User's voice preference
    """
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return VoicePreferenceResponse(
            user_id=str(user.id),
            voice_id=user.preferred_voice_id,
            gender=user.voice_gender,
            style=user.voice_style,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice preference: {str(e)}",
        )


@router.get(
    "/voices",
    response_model=AvailableVoicesResponse,
    summary="Get available voices",
)
async def get_available_voices(
    language: str = "en",
    provider: str = "elevenlabs",
    db: AsyncSession = Depends(get_db),
) -> AvailableVoicesResponse:
    """
    Get available voices for a language and provider.

    Args:
        language: Language code (e.g., 'en', 'hi')
        provider: TTS provider (elevenlabs, azure, amazon)
        db: Database session

    Returns:
        List of available voices
    """
    try:
        tts_service = TTSService(provider=TTSProvider(provider))
        voices = tts_service.get_available_voices(language=language, provider=provider)

        # Convert to schema
        voice_configs = [
            VoiceConfig(
                voice_id=voice.voice_id,
                name=voice.name,
                language=voice.language,
                gender=voice.gender,
                style=voice.style,
            )
            for voice in voices
        ]

        return AvailableVoicesResponse(voices=voice_configs)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available voices: {str(e)}",
        )


@router.post(
    "/flow",
    response_model=VoiceFlowResponse,
    status_code=status.HTTP_200_OK,
    summary="Voice flow: STT → LangGraph → TTS",
)
async def voice_flow(
    body: VoiceFlowRequest,
    db: AsyncSession = Depends(get_db),
) -> VoiceFlowResponse:
    """
    Process voice input through the complete voice flow.

    This endpoint:
    1. Transcribes audio input to text (STT)
    2. Passes transcribed text through LangGraph
    3. Converts text response to audio (TTS)
    4. Returns audio output to client

    Args:
        body: Voice flow request with audio data
        db: Database session

    Returns:
        Voice flow response with audio output
    """
    import time
    from uuid import UUID

    try:
        start_time = time.time()

        # Decode audio data
        audio_data = base64.b64decode(body.audio_data)

        # Get customer profile if user_id provided
        customer_profile = {}
        if body.user_id:
            try:
                result = await db.execute(
                    select(User).where(User.id == UUID(body.user_id))
                )
                user = result.scalar_one_or_none()
                if user:
                    customer_profile = {
                        "preferred_voice_id": user.preferred_voice_id,
                        "voice_gender": user.voice_gender,
                        "voice_style": user.voice_style,
                        "preferred_language": user.preferred_language,
                    }
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")

        # Initialize STT service
        stt_service = STTService(provider=STTProvider.whisper)

        # Step 1: STT - Transcribe audio to text
        transcription_result = stt_service.transcribe(
            audio_data=audio_data,
            audio_format=body.audio_format,
            use_chunked=True,
            apply_noise_reduction=True,
        )

        # Step 2: LangGraph - Process transcribed text
        # For now, use a simple placeholder response
        # In production, this would call the actual LangGraph flow
        text_response = f"I heard you say: {transcription_result.text}. This is a placeholder response from the AI."

        # Step 3: TTS - Convert text response to audio
        tts_service = TTSService(provider=TTSProvider.elevenlabs)

        # Get voice preference
        voice_id = customer_profile.get("preferred_voice_id")
        language = customer_profile.get("preferred_language") or "en"

        tts_result = tts_service.synthesize(
            text=text_response,
            voice_id=voice_id,
            language=language,
            use_ssml=True,
        )

        # Convert audio to base64
        audio_output_base64 = base64.b64encode(tts_result.audio_data).decode("utf-8")

        total_time_ms = (time.time() - start_time) * 1000

        return VoiceFlowResponse(
            transcription=transcription_result.text,
            transcription_confidence=transcription_result.confidence,
            text_response=text_response,
            audio_output=audio_output_base64,
            audio_format=tts_result.audio_format,
            audio_duration=tts_result.duration,
            voice_id=tts_result.voice_id,
            stt_provider=transcription_result.provider,
            tts_provider=tts_result.provider,
            processing_time_ms=total_time_ms,
        )

    except Exception as e:
        logger.exception(f"Voice flow failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice flow failed: {str(e)}",
        )
