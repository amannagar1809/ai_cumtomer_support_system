"""User preferences API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user_preferences import (
    LanguagePreferenceResponse,
    SetLanguagePreferenceRequest,
    SupportedLanguagesResponse,
)
from app.services.langgraph.language_preference_service import LanguagePreferenceService

router = APIRouter(prefix="/user/preferences", tags=["user_preferences"])


@router.get(
    "/language",
    response_model=LanguagePreferenceResponse,
    summary="Get user's language preference",
)
async def get_language_preference(
    user_id: UUID = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
) -> LanguagePreferenceResponse:
    """
    Get the user's preferred language.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        User's language preference
    """
    preference_service = LanguagePreferenceService(db)
    preferred_language = await preference_service.get_user_preference(str(user_id))

    return LanguagePreferenceResponse(
        user_id=str(user_id),
        preferred_language=preferred_language,
    )


@router.post(
    "/language",
    response_model=LanguagePreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Set user's language preference",
)
async def set_language_preference(
    body: SetLanguagePreferenceRequest,
    db: AsyncSession = Depends(get_db),
) -> LanguagePreferenceResponse:
    """
    Set the user's preferred language manually.

    Args:
        body: Language preference request
        db: Database session

    Returns:
        Updated language preference
    """
    preference_service = LanguagePreferenceService(db)
    success = await preference_service.set_user_preference(
        user_id=str(body.user_id),
        language_code=body.language_code,
        source="manual",
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to set language preference. Check if language is supported.",
        )

    return LanguagePreferenceResponse(
        user_id=str(body.user_id),
        preferred_language=body.language_code,
    )


@router.delete(
    "/language",
    response_model=LanguagePreferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear user's language preference",
)
async def clear_language_preference(
    user_id: UUID = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
) -> LanguagePreferenceResponse:
    """
    Clear the user's preferred language (reset to auto-detection).

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Cleared language preference (None)
    """
    preference_service = LanguagePreferenceService(db)
    success = await preference_service.clear_user_preference(str(user_id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to clear language preference.",
        )

    return LanguagePreferenceResponse(
        user_id=str(user_id),
        preferred_language=None,
    )


@router.get(
    "/languages/supported",
    response_model=SupportedLanguagesResponse,
    summary="Get supported languages",
)
async def get_supported_languages(
    db: AsyncSession = Depends(get_db),
) -> SupportedLanguagesResponse:
    """
    Get list of supported languages.

    Args:
        db: Database session

    Returns:
        List of supported languages
    """
    preference_service = LanguagePreferenceService(db)
    supported_languages = preference_service.get_supported_languages()

    return SupportedLanguagesResponse(
        languages=supported_languages,
    )
