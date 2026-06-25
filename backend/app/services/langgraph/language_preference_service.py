"""Language preference service for persisting and managing user language preferences."""

import logging
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.langgraph.language_detector import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# Consistency threshold for auto-updating language preference
CONSISTENCY_THRESHOLD = 5  # Number of consistent detections before auto-update

# Language preference sources
PREFERENCE_SOURCE_MANUAL = "manual"
PREFERENCE_SOURCE_AUTO = "auto"
PREFERENCE_SOURCE_DETECTED = "detected"


class LanguagePreferenceService:
    """Service for managing user language preferences."""

    def __init__(self, db_session: AsyncSession):
        """
        Initialize language preference service.

        Args:
            db_session: Database session
        """
        self.logger = logger
        self.db_session = db_session

    async def get_user_preference(self, user_id: str) -> Optional[str]:
        """
        Get user's preferred language from database.

        Args:
            user_id: User ID

        Returns:
            Preferred language code or None if not set
        """
        try:
            result = await self.db_session.execute(
                select(User.preferred_language).where(User.id == user_id)
            )
            preferred_language = result.scalar_one_or_none()
            return preferred_language
        except Exception as e:
            logger.error(f"Error getting user preference: {e}")
            return None

    async def set_user_preference(
        self,
        user_id: str,
        language_code: str,
        source: str = PREFERENCE_SOURCE_MANUAL,
    ) -> bool:
        """
        Set user's preferred language in database.

        Args:
            user_id: User ID
            language_code: Language code (e.g., 'en', 'hi')
            source: Source of preference (manual, auto, detected)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate language code
            if language_code not in SUPPORTED_LANGUAGES:
                logger.warning(f"Unsupported language code: {language_code}")
                return False

            # Update user preference
            result = await self.db_session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User not found: {user_id}")
                return False

            user.preferred_language = language_code
            user.language_preference_source = source
            user.language_preference_updated_at = datetime.now(UTC)

            await self.db_session.commit()
            await self.db_session.refresh(user)

            logger.info(
                f"User preference updated: {user_id} -> {language_code} (source: {source})"
            )
            return True

        except Exception as e:
            logger.error(f"Error setting user preference: {e}")
            await self.db_session.rollback()
            return False

    async def should_auto_update_preference(
        self,
        user_id: str,
        detected_language: str,
        consistency_count: int,
    ) -> bool:
        """
        Determine if language preference should be auto-updated based on consistency.

        Args:
            user_id: User ID
            detected_language: Consistently detected language
            consistency_count: Number of consistent detections

        Returns:
            True if should auto-update, False otherwise
        """
        try:
            # Get current preference
            current_preference = await self.get_user_preference(user_id)

            # Don't auto-update if user manually set preference
            if current_preference:
                result = await self.db_session.execute(
                    select(User.language_preference_source).where(User.id == user_id)
                )
                source = result.scalar_one_or_none()
                if source == PREFERENCE_SOURCE_MANUAL:
                    logger.info(f"Skipping auto-update for user {user_id} (manual preference set)")
                    return False

            # Check consistency threshold
            if consistency_count >= CONSISTENCY_THRESHOLD:
                logger.info(
                    f"Consistency threshold reached for user {user_id}: "
                    f"{consistency_count} detections of {detected_language}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking auto-update condition: {e}")
            return False

    async def auto_update_preference(
        self,
        user_id: str,
        detected_language: str,
    ) -> bool:
        """
        Auto-update user's language preference based on consistent detection.

        Args:
            user_id: User ID
            detected_language: Consistently detected language

        Returns:
            True if successful, False otherwise
        """
        try:
            return await self.set_user_preference(
                user_id=user_id,
                language_code=detected_language,
                source=PREFERENCE_SOURCE_AUTO,
            )
        except Exception as e:
            logger.error(f"Error auto-updating preference: {e}")
            return False

    async def clear_user_preference(self, user_id: str) -> bool:
        """
        Clear user's preferred language (reset to auto-detection).

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.db_session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User not found: {user_id}")
                return False

            user.preferred_language = None
            user.language_preference_source = None
            user.language_preference_updated_at = datetime.now(UTC)

            await self.db_session.commit()
            await self.db_session.refresh(user)

            logger.info(f"User preference cleared: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing user preference: {e}")
            await self.db_session.rollback()
            return False

    def is_supported_language(self, language_code: str) -> bool:
        """
        Check if a language code is supported.

        Args:
            language_code: Language code to check

        Returns:
            True if language is supported
        """
        return language_code in SUPPORTED_LANGUAGES

    def get_supported_languages(self) -> dict[str, str]:
        """
        Get list of supported languages.

        Returns:
            Dictionary of language codes to language names
        """
        return SUPPORTED_LANGUAGES.copy()
