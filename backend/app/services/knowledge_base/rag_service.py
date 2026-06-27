"""RAG (Retrieval-Augmented Generation) service for knowledge base."""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# RAG configuration
SIMILARITY_THRESHOLD = 0.70  # Minimum cosine similarity for relevant chunks
TOP_K_CHUNKS = 5  # Number of top chunks to retrieve
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI embedding model
EMBEDDING_DIMENSION = 1536  # OpenAI ada-002 dimension


class RetrievedChunk(BaseModel):
    """A retrieved chunk from knowledge base."""

    chunk_id: str = Field(description="Chunk ID")
    document_id: str = Field(description="Document ID")
    text: str = Field(description="Chunk text content")
    similarity_score: float = Field(description="Cosine similarity score")
    source_document: str = Field(description="Source document filename")
    category: str = Field(description="Knowledge category")
    version: str = Field(description="Document version")
    chunk_index: int = Field(description="Chunk index in document")


class RAGResult(BaseModel):
    """Result of RAG retrieval."""

    query: str = Field(description="Original user query")
    chunks_retrieved: list[RetrievedChunk] = Field(description="Retrieved chunks")
    retrieval_success: bool = Field(description="Whether retrieval was successful")
    chunks_above_threshold: int = Field(description="Number of chunks above similarity threshold")
    top_similarity: float = Field(default=0.0, description="Highest similarity score")
    avg_similarity: float = Field(default=0.0, description="Average similarity score")
    category_filtered: Optional[str] = Field(default=None, description="Category filter applied")
    retrieval_time_ms: float = Field(description="Retrieval time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Retrieval timestamp")


class RAGService:
    """Service for RAG retrieval from knowledge base."""

    def __init__(
        self,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        top_k: int = TOP_K_CHUNKS,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        """
        Initialize RAG service.

        Args:
            similarity_threshold: Minimum similarity threshold (0.70)
            top_k: Number of top chunks to retrieve
            embedding_model: Embedding model to use
        """
        self.logger = logger
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.embedding_model = embedding_model
        self._initialize_embedding_client()

    def _initialize_embedding_client(self):
        """Initialize the embedding client."""
        try:
            # Placeholder for actual embedding client initialization
            # In production, this would initialize OpenAI client or local model
            logger.info(f"Embedding client initialized: {self.embedding_model} (placeholder mode)")
            self.embedding_client = "placeholder"
        except Exception as e:
            logger.error(f"Failed to initialize embedding client: {e}")
            self.embedding_client = None

    def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> RAGResult:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: User query text
            category: Optional category filter
            top_k: Optional override for top_k

        Returns:
            RAG result with retrieved chunks
        """
        import time

        start_time = time.time()
        top_k = top_k or self.top_k

        try:
            # Generate query embedding
            query_embedding = self._generate_query_embedding(query)

            # Import vector store (avoid circular import)
            from app.services.knowledge_base.vector_store import VectorStore, VectorDBProvider

            # Initialize vector store
            vector_store = VectorStore(provider=VectorDBProvider.pgvector)

            # Search for similar chunks
            search_results = vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                category=category,
            )

            # Filter by similarity threshold
            relevant_chunks = [
                RetrievedChunk(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    text=result.text,
                    similarity_score=result.score,
                    source_document=result.metadata.get("source_document", "unknown"),
                    category=result.metadata.get("category", "unknown"),
                    version=result.metadata.get("version", "1.0"),
                    chunk_index=result.metadata.get("chunk_index", 0),
                )
                for result in search_results
                if result.score >= self.similarity_threshold
            ]

            # Calculate statistics
            retrieval_success = len(relevant_chunks) > 0
            chunks_above_threshold = len(relevant_chunks)
            top_similarity = max([c.similarity_score for c in relevant_chunks]) if relevant_chunks else 0.0
            avg_similarity = (
                sum([c.similarity_score for c in relevant_chunks]) / len(relevant_chunks)
                if relevant_chunks
                else 0.0
            )

            retrieval_time_ms = (time.time() - start_time) * 1000

            # Create result
            result = RAGResult(
                query=query,
                chunks_retrieved=relevant_chunks,
                retrieval_success=retrieval_success,
                chunks_above_threshold=chunks_above_threshold,
                top_similarity=top_similarity,
                avg_similarity=avg_similarity,
                category_filtered=category,
                retrieval_time_ms=retrieval_time_ms,
            )

            # Log retrieval for analytics
            self._log_retrieval(result)

            logger.info(
                f"RAG retrieval: {len(relevant_chunks)} chunks above threshold "
                f"(threshold: {self.similarity_threshold}), "
                f"top similarity: {top_similarity:.3f}, "
                f"time: {retrieval_time_ms:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            retrieval_time_ms = (time.time() - start_time) * 1000

            return RAGResult(
                query=query,
                chunks_retrieved=[],
                retrieval_success=False,
                chunks_above_threshold=0,
                top_similarity=0.0,
                avg_similarity=0.0,
                category_filtered=category,
                retrieval_time_ms=retrieval_time_ms,
            )

    def _generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding for query text.

        Args:
            query: Query text

        Returns:
            Embedding vector
        """
        # Placeholder implementation
        # In production, this would call OpenAI embedding API or local model
        # For now, return placeholder embedding (zeros of correct dimension)
        return [0.0] * EMBEDDING_DIMENSION

    def _log_retrieval(self, result: RAGResult):
        """
        Log retrieval result for analytics.

        Args:
            result: RAG result to log
        """
        # In production, this would log to analytics system
        logger.info(
            f"RAG Analytics: query='{result.query[:50]}...', "
            f"success={result.retrieval_success}, "
            f"chunks={result.chunks_above_threshold}, "
            f"top_score={result.top_similarity:.3f}, "
            f"avg_score={result.avg_similarity:.3f}, "
            f"category={result.category_filtered}, "
            f"time_ms={result.retrieval_time_ms:.2f}"
        )

    def build_context_prompt(
        self,
        rag_result: RAGResult,
        include_citations: bool = True,
    ) -> str:
        """
        Build context prompt with retrieved chunks.

        Args:
            rag_result: RAG result with retrieved chunks
            include_citations: Whether to include citations

        Returns:
            Context prompt string
        """
        if not rag_result.retrieval_success or not rag_result.chunks_retrieved:
            return ""

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(rag_result.chunks_retrieved, 1):
            if include_citations:
                citation = f"[{chunk.source_document} - {chunk.category} - v{chunk.version} - Section {chunk.chunk_index + 1}]"
                context_parts.append(f"{citation}\n{chunk.text}")
            else:
                context_parts.append(chunk.text)

        context = "\n\n".join(context_parts)

        # Build full context prompt
        context_prompt = f"""
Based on the following knowledge base information:

{context}

Please use this information to answer the user's question. If the information doesn't contain the answer, say so clearly.
""".strip()

        return context_prompt

    def add_citations_to_response(
        self,
        response: str,
        rag_result: RAGResult,
    ) -> str:
        """
        Add citations to AI response.

        Args:
            response: AI response text
            rag_result: RAG result with retrieved chunks

        Returns:
            Response with citations added
        """
        if not rag_result.retrieval_success or not rag_result.chunks_retrieved:
            return response

        # Build citation string
        citations = []
        for chunk in rag_result.chunks_retrieved:
            citation = f"[{chunk.source_document} - {chunk.category} - v{chunk.version} - Section {chunk.chunk_index + 1}]"
            if citation not in citations:
                citations.append(citation)

        if not citations:
            return response

        citation_text = "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations)

        return response + citation_text
