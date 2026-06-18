"""Message processing utilities for Receive Query node."""

import hashlib
import logging
import re
import unicodedata
from typing import Optional

import bleach

logger = logging.getLogger(__name__)

# Constants
MIN_MESSAGE_LENGTH = 1
MAX_MESSAGE_LENGTH = 2000
DUPLICATE_CHECK_TTL_SECONDS = 300  # 5 minutes


def validate_message_length(message: str) -> tuple[bool, Optional[str]]:
    """
    Validate message length.

    Args:
        message: The message to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not message:
        return False, "Message cannot be empty"

    message_length = len(message)
    if message_length < MIN_MESSAGE_LENGTH:
        return False, f"Message too short (minimum {MIN_MESSAGE_LENGTH} character)"

    if message_length > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (maximum {MAX_MESSAGE_LENGTH} characters)"

    return True, None


def sanitize_message(message: str) -> str:
    """
    Sanitize message by removing HTML, normalizing Unicode, and trimming whitespace.

    Args:
        message: The message to sanitize

    Returns:
        Sanitized message
    """
    # Remove HTML tags using bleach
    sanitized = bleach.clean(message, tags=[], strip=True)

    # Normalize Unicode (NFKC form for compatibility)
    sanitized = unicodedata.normalize("NFKC", sanitized)

    # Trim whitespace
    sanitized = sanitized.strip()

    # Remove excessive whitespace (multiple spaces/tabs/newlines)
    sanitized = re.sub(r"\s+", " ", sanitized)

    return sanitized


def detect_message_type(message: str, metadata: dict) -> str:
    """
    Detect message type (text, image, file, voice).

    Args:
        message: The message content
        metadata: Additional metadata from the message

    Returns:
        Message type string
    """
    # Check metadata for file attachments
    if metadata.get("file_url") or metadata.get("file_type"):
        file_type = metadata.get("file_type", "").lower()

        if file_type.startswith("image/"):
            return "image"
        elif file_type.startswith("audio/") or file_type.startswith("voice/"):
            return "voice"
        else:
            return "file"

    # Check for image URLs in message
    image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]
    if any(ext in message.lower() for ext in image_extensions):
        return "image"

    # Check for voice/audio indicators
    voice_keywords = ["voice note", "audio message", "voice message", "voice recording"]
    if any(keyword in message.lower() for keyword in voice_keywords):
        return "voice"

    # Default to text
    return "text"


def generate_message_hash(message: str, user_id: Optional[str], conversation_id: Optional[str]) -> str:
    """
    Generate a hash for duplicate detection.

    Args:
        message: The message content
        user_id: The user ID
        conversation_id: The conversation ID

    Returns:
        SHA256 hash string
    """
    # Create a unique string combining message, user, and conversation
    unique_string = f"{message}:{user_id}:{conversation_id}"

    # Generate SHA256 hash
    hash_object = hashlib.sha256(unique_string.encode())
    return hash_object.hexdigest()


async def check_duplicate_message(
    message_hash: str,
    redis_client,
    ttl_seconds: int = DUPLICATE_CHECK_TTL_SECONDS,
) -> bool:
    """
    Check if message is a duplicate using Redis.

    Args:
        message_hash: The hash of the message
        redis_client: Redis client instance
        ttl_seconds: Time to live for the duplicate check key

    Returns:
        True if duplicate, False otherwise
    """
    try:
        key = f"msg_duplicate:{message_hash}"

        # Check if key exists
        exists = await redis_client.exists(key)

        if exists:
            logger.info(f"Duplicate message detected: {message_hash[:16]}...")
            return True

        # Set the key with TTL
        await redis_client.setex(key, ttl_seconds, "1")
        return False

    except Exception as e:
        logger.error(f"Error checking duplicate message: {e}")
        # Fail open - if Redis is down, allow the message through
        return False


def calculate_queue_priority(
    sentiment: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    message_type: str = "text",
) -> int:
    """
    Calculate queue priority based on sentiment and message type.

    Priority scale: 1-10 (higher = more urgent)

    Args:
        sentiment: Detected sentiment (positive, negative, neutral)
        sentiment_score: Sentiment score (-1 to 1)
        message_type: Type of message (text, image, file, voice)

    Returns:
        Priority value (1-10)
    """
    base_priority = 5

    # Adjust based on sentiment
    if sentiment == "negative":
        # Negative sentiment gets higher priority
        if sentiment_score and sentiment_score < -0.5:
            base_priority += 3  # Very negative = priority 8
        else:
            base_priority += 2  # Negative = priority 7
    elif sentiment == "positive":
        # Positive sentiment gets lower priority
        base_priority -= 1  # Positive = priority 4
    # Neutral stays at base priority

    # Adjust based on message type
    if message_type == "voice":
        base_priority += 1  # Voice messages get slight priority boost
    elif message_type == "image":
        base_priority += 0  # Images stay at current priority
    elif message_type == "file":
        base_priority -= 1  # Files get lower priority

    # Ensure priority is within bounds
    return max(1, min(10, base_priority))


def extract_message_metadata(
    timestamp,
    channel: str,
    user_id: Optional[str],
    conversation_id: Optional[str],
    additional_metadata: dict,
) -> dict:
    """
    Extract and standardize message metadata.

    Args:
        timestamp: Message timestamp
        channel: Communication channel
        user_id: User ID
        conversation_id: Conversation ID
        additional_metadata: Additional channel-specific metadata

    Returns:
        Standardized metadata dictionary
    """
    return {
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        "channel": channel,
        "user_id": str(user_id) if user_id else None,
        "conversation_id": str(conversation_id) if conversation_id else None,
        **additional_metadata,
    }
