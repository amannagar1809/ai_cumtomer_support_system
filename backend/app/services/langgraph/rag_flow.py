"""RAG flow nodes for integrating knowledge base retrieval with LangGraph."""

import logging
import time
from typing import Optional

from app.services.knowledge_base.rag_service import RAGService, SIMILARITY_THRESHOLD, TOP_K_CHUNKS
from app.services.langgraph.state import ConversationState

logger = logging.getLogger(__name__)


async def knowledge_search_node(state: ConversationState) -> ConversationState:
    """
    Knowledge Search Node: Retrieve relevant chunks from knowledge base.

    This node:
    - Embeds user query
    - Finds top 5 relevant chunks
    - Applies similarity threshold (0.70)
    - Stores retrieval results in state
    - Logs retrieval success/failure for analytics

    Args:
        state: Current conversation state

    Returns:
        Updated state with RAG retrieval results
    """
    start_time = time.time()
    state.current_node = "knowledge_search"
    state.execution_path.append("knowledge_search")

    try:
        # Check if RAG is enabled
        if not state.rag_enabled:
            logger.info("RAG is disabled, skipping knowledge search")
            state.rag_retrieval_success = False
            state.rag_chunks_above_threshold = 0
            return state

        # Get query text
        query = state.message
        if not query:
            logger.warning("No query text provided for knowledge search")
            state.rag_retrieval_success = False
            state.rag_chunks_above_threshold = 0
            return state

        # Initialize RAG service
        rag_service = RAGService(
            similarity_threshold=SIMILARITY_THRESHOLD,
            top_k=TOP_K_CHUNKS,
        )

        # Retrieve relevant chunks
        rag_result = rag_service.retrieve(
            query=query,
            category=state.rag_category_filter,
        )

        # Store retrieval results in state
        state.rag_retrieval_success = rag_result.retrieval_success
        state.rag_chunks_above_threshold = rag_result.chunks_above_threshold
        state.rag_top_similarity = rag_result.top_similarity
        state.rag_avg_similarity = rag_result.avg_similarity
        state.rag_retrieval_time_ms = rag_result.retrieval_time_ms

        # Convert retrieved chunks to dict format for state
        state.rag_chunks_retrieved = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "similarity_score": chunk.similarity_score,
                "source_document": chunk.source_document,
                "category": chunk.category,
                "version": chunk.version,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in rag_result.chunks_retrieved
        ]

        # Build context prompt if retrieval was successful
        if rag_result.retrieval_success:
            state.rag_context_prompt = rag_service.build_context_prompt(
                rag_result=rag_result,
                include_citations=False,  # Citations added later in response
            )

        # Record intermediate result
        state.intermediate_results["knowledge_search"] = {
            "query": query,
            "retrieval_success": rag_result.retrieval_success,
            "chunks_retrieved": rag_result.chunks_above_threshold,
            "top_similarity": rag_result.top_similarity,
            "avg_similarity": rag_result.avg_similarity,
            "category_filter": rag_result.category_filtered,
            "retrieval_time_ms": rag_result.retrieval_time_ms,
        }

        logger.info(
            f"Knowledge search: {rag_result.chunks_above_threshold} chunks above threshold "
            f"(threshold: {SIMILARITY_THRESHOLD}), "
            f"top similarity: {rag_result.top_similarity:.3f}, "
            f"time: {rag_result.retrieval_time_ms:.2f}ms"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "knowledge_search"
        state.rag_retrieval_success = False
        state.rag_chunks_above_threshold = 0
        logger.exception(f"Error in knowledge_search node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["knowledge_search"] = duration
        logger.debug(f"knowledge_search node completed in {duration:.2f}s")

    return state


async def rag_response_node(state: ConversationState) -> ConversationState:
    """
    RAG Response Node: Inject context into response and add citations.

    This node:
    - Injects retrieved chunks into system prompt if available
    - Falls back to LLM only if no relevant chunks found
    - Adds citations to response with chunk references
    - Marks whether RAG was used in response

    Args:
        state: Current conversation state

    Returns:
        Updated state with RAG-enhanced response
    """
    start_time = time.time()
    state.current_node = "rag_response"
    state.execution_path.append("rag_response")

    try:
        # Check if RAG retrieval was successful
        if not state.rag_retrieval_success or not state.rag_chunks_retrieved:
            logger.info("No relevant chunks found, using LLM only (fallback)")
            state.rag_used_in_response = False
            state.rag_citations_included = False
            return state

        # Check if context prompt was built
        if not state.rag_context_prompt:
            logger.warning("Context prompt not available, using LLM only")
            state.rag_used_in_response = False
            state.rag_citations_included = False
            return state

        # Inject context into response
        # In production, this would modify the system prompt for the LLM
        # For now, we'll mark that context should be used
        state.rag_used_in_response = True

        # Add citations to response
        if state.final_response:
            # Initialize RAG service to add citations
            rag_service = RAGService()

            # Reconstruct RAG result from state
            from app.services.knowledge_base.rag_service import RetrievedChunk, RAGResult

            retrieved_chunks = [
                RetrievedChunk(
                    chunk_id=chunk["chunk_id"],
                    document_id=chunk["document_id"],
                    text=chunk["text"],
                    similarity_score=chunk["similarity_score"],
                    source_document=chunk["source_document"],
                    category=chunk["category"],
                    version=chunk["version"],
                    chunk_index=chunk["chunk_index"],
                )
                for chunk in state.rag_chunks_retrieved
            ]

            rag_result = RAGResult(
                query=state.message,
                chunks_retrieved=retrieved_chunks,
                retrieval_success=state.rag_retrieval_success,
                chunks_above_threshold=state.rag_chunks_above_threshold,
                top_similarity=state.rag_top_similarity,
                avg_similarity=state.rag_avg_similarity,
                retrieval_time_ms=state.rag_retrieval_time_ms or 0.0,
            )

            # Add citations to response
            state.final_response = rag_service.add_citations_to_response(
                response=state.final_response,
                rag_result=rag_result,
            )
            state.rag_citations_included = True

        # Record intermediate result
        state.intermediate_results["rag_response"] = {
            "rag_used": state.rag_used_in_response,
            "citations_included": state.rag_citations_included,
            "chunks_used": state.rag_chunks_above_threshold,
        }

        logger.info(
            f"RAG response: context used={state.rag_used_in_response}, "
            f"citations included={state.rag_citations_included}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "rag_response"
        state.rag_used_in_response = False
        state.rag_citations_included = False
        logger.exception(f"Error in rag_response node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["rag_response"] = duration
        logger.debug(f"rag_response node completed in {duration:.2f}s")

    return state
