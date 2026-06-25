"""User preferences schemas."""

from pydantic import BaseModel, Field


class SetLanguagePreferenceRequest(BaseModel):
    """Request to set user's language preference."""

    user_id: str = Field(..., description="User ID")
    language_code: str = Field(..., description="Language code (e.g., 'en', 'hi', 'es', 'fr', 'ar', 'de')")


class LanguagePreferenceResponse(BaseModel):
    """Response with user's language preference."""

    user_id: str = Field(..., description="User ID")
    preferred_language: str | None = Field(..., description="Preferred language code or None if not set")


class SupportedLanguagesResponse(BaseModel):
    """Response with supported languages."""

    languages: dict[str, str] = Field(..., description="Dictionary of language codes to language names")
