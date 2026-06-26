"""Language-aware knowledge base search service."""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.services.knowledge_base.document_translator import DocumentTranslator

logger = logging.getLogger(__name__)


class KnowledgeSearchResult(BaseModel):
    """Result of knowledge base search."""

    document_id: str = Field(description="Document ID")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content")
    language: str = Field(description="Document language code")
    category: Optional[str] = Field(default=None, description="Document category")
    relevance_score: float = Field(description="Relevance score (0.0 to 1.0)")
    is_fallback: bool = Field(default=False, description="Whether this is a fallback result from English")
    translation_note: Optional[str] = Field(default=None, description="Translation note if fallback")


class LanguageAwareKnowledgeSearch:
    """Service for language-aware knowledge base search."""

    def __init__(self):
        """Initialize language-aware knowledge search service."""
        self.logger = logger
        self.document_translator = DocumentTranslator()

    def search(
        self,
        query: str,
        user_language: str,
        top_k: int = 5,
    ) -> list[KnowledgeSearchResult]:
        """
        Search knowledge base with language awareness.

        Args:
            query: Search query
            user_language: User's language code
            top_k: Number of results to return

        Returns:
            List of knowledge search results
        """
        # First, try to search in user's language
        native_results = self._search_by_language(
            query=query,
            language=user_language,
            top_k=top_k,
        )

        # If we have results in user's language, return them
        if native_results:
            logger.info(
                f"Found {len(native_results)} results in user's language: {user_language}"
            )
            return native_results

        # No results in user's language, fall back to English
        logger.info(
            f"No results found in {user_language}, falling back to English"
        )
        english_results = self._search_by_language(
            query=query,
            language="en",
            top_k=top_k,
        )

        # Add translation note to English results
        translation_note = self.document_translator.get_translation_note(user_language)

        fallback_results = [
            KnowledgeSearchResult(
                document_id=result.document_id,
                title=result.title,
                content=result.content,
                language=result.language,
                category=result.category,
                relevance_score=result.relevance_score,
                is_fallback=True,
                translation_note=translation_note,
            )
            for result in english_results
        ]

        return fallback_results

    def _search_by_language(
        self,
        query: str,
        language: str,
        top_k: int,
    ) -> list[KnowledgeSearchResult]:
        """
        Search knowledge base for documents in a specific language.

        Args:
            query: Search query
            language: Language code to filter by
            top_k: Number of results to return

        Returns:
            List of knowledge search results
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Use vector search (e.g., Pinecone, Weaviate)
        # 2. Filter by language
        # 3. Return top-k results with relevance scores

        # For now, return empty results
        # This would be replaced with actual vector search implementation
        logger.debug(f"Searching for documents in language: {language}")

        return []

    def search_with_priority(
        self,
        query: str,
        user_language: str,
        top_k: int = 5,
    ) -> list[KnowledgeSearchResult]:
        """
        Search knowledge base with language priority.

        Prioritizes native language content but includes English if needed.

        Args:
            query: Search query
            user_language: User's language code
            top_k: Number of results to return

        Returns:
            List of knowledge search results with native language prioritized
        """
        # Search in user's language
        native_results = self._search_by_language(
            query=query,
            language=user_language,
            top_k=top_k,
        )

        # Search in English as backup
        english_results = self._search_by_language(
            query=query,
            language="en",
            top_k=top_k,
        )

        # If user language is English, just return English results
        if user_language == "en":
            return english_results

        # If we have enough native results, return them
        if len(native_results) >= top_k:
            return native_results

        # Mix native and English results, prioritizing native
        mixed_results = native_results.copy()

        # Add English results to fill up to top_k
        remaining_slots = top_k - len(mixed_results)
        for english_result in english_results[:remaining_slots]:
            translation_note = self.document_translator.get_translation_note(user_language)
            mixed_results.append(
                KnowledgeSearchResult(
                    document_id=english_result.document_id,
                    title=english_result.title,
                    content=english_result.content,
                    language=english_result.language,
                    category=english_result.category,
                    relevance_score=english_result.relevance_score,
                    is_fallback=True,
                    translation_note=translation_note,
                )
            )

        return mixed_results
