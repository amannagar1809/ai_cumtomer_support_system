"""Voice flow nodes for integrating STT and TTS with LangGraph."""

import base64
import logging
import time
from typing import Optional

from app.services.langgraph.state import ConversationState
from app.services.voice.stt_service import STTService, STTProvider
from app.services.voice.tts_service import TTSService, TTSProvider

logger = logging.getLogger(__name__)


async def voice_input_node(state: ConversationState) -> ConversationState:
    """
    Voice Input Node: Transcribes audio input to text using STT.

    This node:
    - Takes audio input from state
    - Transcribes using STT service
    - Stores transcription result
    - Preserves original audio for quality monitoring
    - Passes transcribed text to main LangGraph flow

    Args:
        state: Current conversation state

    Returns:
        Updated state with transcription result
    """
    start_time = time.time()
    state.current_node = "voice_input"
    state.execution_path.append("voice_input")

    try:
        # Check if this is a voice flow
        if not state.audio_input_data:
            logger.warning("No audio input data provided")
            state.error = "No audio input data provided"
            state.failed_node = "voice_input"
            return state

        # Initialize STT service
        stt_service = STTService(provider=STTProvider.whisper)

        # Transcribe audio
        audio_format = state.audio_input_format or "mp3"
        transcription_result = stt_service.transcribe(
            audio_data=state.audio_input_data,
            audio_format=audio_format,
            use_chunked=True,
            apply_noise_reduction=True,
        )

        # Store transcription result
        state.transcription_result = transcription_result.text
        state.transcription_confidence = transcription_result.confidence
        state.audio_input_duration = transcription_result.duration
        state.stt_provider = transcription_result.provider

        # Pass transcribed text to main flow
        state.message = transcription_result.text
        state.message_type = "voice"
        state.is_voice_flow = True

        # Record intermediate result
        state.intermediate_results["voice_input"] = {
            "transcription": transcription_result.text,
            "confidence": transcription_result.confidence,
            "duration": transcription_result.duration,
            "provider": transcription_result.provider,
            "processing_time_ms": transcription_result.processing_time_ms,
            "is_chunked": transcription_result.is_chunked,
            "from_cache": transcription_result.from_cache,
            "regional_endpoint": transcription_result.regional_endpoint,
            "latency_target_met": transcription_result.latency_target_met,
        }

        logger.info(
            f"Voice input transcribed: {len(transcription_result.text)} chars, "
            f"confidence: {transcription_result.confidence:.2f}, "
            f"duration: {transcription_result.duration:.2f}s, "
            f"time: {transcription_result.processing_time_ms:.2f}ms"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "voice_input"
        logger.exception(f"Error in voice_input node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["voice_input"] = duration
        logger.debug(f"voice_input node completed in {duration:.2f}s")

    return state


async def voice_output_node(state: ConversationState) -> ConversationState:
    """
    Voice Output Node: Converts text response to audio using TTS.

    This node:
    - Takes final text response from state
    - Converts to audio using TTS service
    - Stores audio output data
    - Returns audio to client
    - Uses user's preferred voice if available

    Args:
        state: Current conversation state

    Returns:
        Updated state with audio output
    """
    start_time = time.time()
    state.current_node = "voice_output"
    state.execution_path.append("voice_output")

    try:
        # Check if this is a voice flow
        if not state.is_voice_flow:
            logger.info("Not a voice flow, skipping TTS")
            return state

        # Get text response
        text_to_speak = state.final_response or state.generated_response
        if not text_to_speak:
            logger.warning("No text response available for TTS")
            return state

        # Get user's preferred voice
        voice_id = None
        if state.customer_profile:
            voice_id = state.customer_profile.get("preferred_voice_id")

        # Get language
        language = state.detected_language or "en"

        # Initialize TTS service
        tts_service = TTSService(provider=TTSProvider.elevenlabs)

        # Synthesize audio
        tts_result = tts_service.synthesize(
            text=text_to_speak,
            voice_id=voice_id,
            language=language,
            use_ssml=True,
        )

        # Store audio output
        state.audio_output_data = tts_result.audio_data
        state.audio_output_format = tts_result.audio_format
        state.audio_output_duration = tts_result.duration
        state.voice_id_used = tts_result.voice_id
        state.tts_provider = tts_result.provider

        # Record intermediate result
        state.intermediate_results["voice_output"] = {
            "text_length": len(text_to_speak),
            "audio_format": tts_result.audio_format,
            "duration": tts_result.duration,
            "voice_id": tts_result.voice_id,
            "provider": tts_result.provider,
            "processing_time_ms": tts_result.processing_time_ms,
            "is_streamed": tts_result.is_streamed,
            "from_cache": tts_result.from_cache,
            "used_ssml": tts_result.used_ssml,
        }

        logger.info(
            f"Voice output synthesized: {len(text_to_speak)} chars, "
            f"duration: {tts_result.duration:.2f}s, "
            f"voice: {tts_result.voice_id}, "
            f"time: {tts_result.processing_time_ms:.2f}ms"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "voice_output"
        logger.exception(f"Error in voice_output node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["voice_output"] = duration
        logger.debug(f"voice_output node completed in {duration:.2f}s")

    return state
