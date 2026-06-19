"""Context management for conversation history and context window."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.message import Message, SenderType

logger = logging.getLogger(__name__)

# Context window configuration
MAX_RECENT_MESSAGES = 10
MAX_CONTEXT_TOKENS = 4000  # Adjust based on LLM model
SUMMARY_TOKEN_LIMIT = 500
CONTEXT_BRANCH_THRESHOLD = 0.6  # Similarity threshold for detecting conversation branches


class MessageRole(str, Enum):
    """Message roles in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationTurn(BaseModel):
    """A single conversation turn with role and content."""

    role: MessageRole = Field(description="Role of the message sender")
    content: str = Field(description="Content of the message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Message timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")


class ConversationSummary(BaseModel):
    """Summary of older conversation messages."""

    summary: str = Field(description="Summary of the conversation")
    topics: list[str] = Field(default_factory=list, description="Key topics discussed")
    entities: dict[str, Any] = Field(default_factory=dict, description="Entities mentioned")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When summary was created")
    message_count: int = Field(description="Number of messages summarized")


class ConversationContext(BaseModel):
    """Complete conversation context including recent messages and summary."""

    conversation_id: str = Field(description="Conversation ID")
    recent_messages: list[ConversationTurn] = Field(default_factory=list, description="Last N messages")
    summary: Optional[ConversationSummary] = Field(default=None, description="Summary of older messages")
    total_message_count: int = Field(default=0, description="Total messages in conversation")
    context_window_tokens: int = Field(default=0, description="Estimated token count of context")
    has_conversation_branch: bool = Field(default=False, description="Whether conversation branch detected")


class ContextManager:
    """Manages conversation context, history retrieval, and summarization."""

    def __init__(
        self,
        max_recent_messages: int = MAX_RECENT_MESSAGES,
        max_context_tokens: int = MAX_CONTEXT_TOKENS,
        summary_token_limit: int = SUMMARY_TOKEN_LIMIT,
        branch_threshold: float = CONTEXT_BRANCH_THRESHOLD,
    ):
        """
        Initialize the context manager.

        Args:
            max_recent_messages: Maximum number of recent messages to keep in full
            max_context_tokens: Maximum tokens for context window
            summary_token_limit: Token limit for summaries
            branch_threshold: Similarity threshold for detecting conversation branches
        """
        self.max_recent_messages = max_recent_messages
        self.max_context_tokens = max_context_tokens
        self.summary_token_limit = summary_token_limit
        self.branch_threshold = branch_threshold

    async def fetch_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> list[ConversationTurn]:
        """
        Fetch conversation history from database.

        Args:
            conversation_id: The conversation ID
            limit: Maximum number of messages to fetch (None for all)

        Returns:
            List of conversation turns
        """
        import uuid

        try:
            # Convert conversation_id to UUID if it's a string
            conv_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

            async for db in get_db():
                # Query messages from database
                query = select(Message).where(Message.conversation_id == conv_uuid).order_by(Message.timestamp)

                if limit:
                    query = query.limit(limit)

                result = await db.execute(query)
                messages = result.scalars().all()

                # Format as conversation turns
                turns = []
                for msg in messages:
                    # Map SenderType to MessageRole
                    if msg.sender_type == SenderType.customer:
                        role = MessageRole.USER
                    elif msg.sender_type == SenderType.ai:
                        role = MessageRole.ASSISTANT
                    elif msg.sender_type == SenderType.human_agent:
                        role = MessageRole.ASSISTANT
                    else:
                        role = MessageRole.USER

                    turn = ConversationTurn(
                        role=role,
                        content=msg.message,
                        timestamp=msg.timestamp,
                        metadata={
                            "language": msg.language,
                            "sentiment": msg.sentiment,
                            "message_id": str(msg.id),
                        },
                    )
                    turns.append(turn)

                logger.info(f"Fetched {len(turns)} messages for conversation {conversation_id}")
                return turns

        except Exception as e:
            logger.error(f"Failed to fetch conversation history: {e}")
            return []

    async def format_conversation_turns(
        self,
        raw_messages: list[dict[str, Any]],
    ) -> list[ConversationTurn]:
        """
        Format raw database messages as conversation turns.

        Args:
            raw_messages: Raw messages from database

        Returns:
            List of formatted conversation turns
        """
        turns = []
        for msg in raw_messages:
            try:
                # Map database role to MessageRole
                role_str = msg.get("role", "user").lower()
                role = MessageRole.USER if role_str == "user" else MessageRole.ASSISTANT

                turn = ConversationTurn(
                    role=role,
                    content=msg.get("content", ""),
                    timestamp=datetime.fromisoformat(msg.get("timestamp", datetime.now(UTC).isoformat())),
                    metadata=msg.get("metadata", {}),
                )
                turns.append(turn)
            except Exception as e:
                logger.warning(f"Failed to format message: {e}")

        return turns

    async def summarize_conversation(
        self,
        messages: list[ConversationTurn],
        current_llm_client: Any = None,
    ) -> ConversationSummary:
        """
        Summarize older conversation messages using LLM.

        Args:
            messages: Messages to summarize
            current_llm_client: LLM client for summarization (optional)

        Returns:
            Conversation summary
        """
        if not messages:
            return ConversationSummary(summary="No conversation history", message_count=0)

        # TODO: Implement actual LLM-based summarization
        # For now, create a simple placeholder summary
        message_count = len(messages)
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        summary_text = (
            f"Conversation with {message_count} messages. "
            f"User sent {len(user_messages)} messages, assistant sent {len(assistant_messages)} responses. "
            f"Topics discussed: general inquiry."
        )

        # Extract simple entities from messages
        entities = {}
        for msg in messages:
            content_lower = msg.content.lower()
            # Simple entity extraction (can be enhanced)
            if "order" in content_lower:
                entities["mentioned_order"] = True
            if "billing" in content_lower or "payment" in content_lower:
                entities["mentioned_billing"] = True
            if "technical" in content_lower or "error" in content_lower:
                entities["mentioned_technical"] = True

        return ConversationSummary(
            summary=summary_text,
            topics=["general inquiry"],
            entities=entities,
            message_count=message_count,
        )

    def detect_conversation_branch(
        self,
        current_message: str,
        recent_messages: list[ConversationTurn],
    ) -> bool:
        """
        Detect if current message represents a conversation branch (unrelated topic).

        Args:
            current_message: The current user message
            recent_messages: Recent conversation history

        Returns:
            True if conversation branch detected
        """
        if not recent_messages:
            return False

        # Simple keyword-based similarity check
        # TODO: Implement more sophisticated semantic similarity using embeddings
        current_words = set(current_message.lower().split())

        recent_content = " ".join([m.content.lower() for m in recent_messages])
        recent_words = set(recent_content.split())

        # Calculate Jaccard similarity
        if not current_words or not recent_words:
            return False

        intersection = len(current_words & recent_words)
        union = len(current_words | recent_words)
        similarity = intersection / union if union > 0 else 0.0

        # If similarity is below threshold, it's likely a branch
        is_branch = similarity < self.branch_threshold

        if is_branch:
            logger.info(f"Conversation branch detected (similarity: {similarity:.2f})")

        return is_branch

    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4

    def calculate_context_window_tokens(
        self,
        recent_messages: list[ConversationTurn],
        summary: Optional[ConversationSummary] = None,
    ) -> int:
        """
        Calculate total token count for context window.

        Args:
            recent_messages: Recent conversation messages
            summary: Conversation summary

        Returns:
            Total estimated token count
        """
        tokens = 0

        # Count tokens from recent messages
        for msg in recent_messages:
            tokens += self.estimate_token_count(msg.content)

        # Count tokens from summary
        if summary:
            tokens += self.estimate_token_count(summary.summary)
            tokens += len(summary.topics) * 5  # Rough estimate for topics
            tokens += len(str(summary.entities)) // 4  # Rough estimate for entities

        return tokens

    def trim_context_to_fit(
        self,
        context: ConversationContext,
    ) -> ConversationContext:
        """
        Trim context to fit within token limits.

        Args:
            context: Current conversation context

        Returns:
            Trimmed conversation context
        """
        current_tokens = context.context_window_tokens

        if current_tokens <= self.max_context_tokens:
            return context

        # Trim recent messages if over limit
        trimmed_messages = []
        tokens_used = 0

        # Keep most recent messages (reverse order to trim from oldest)
        for msg in reversed(context.recent_messages):
            msg_tokens = self.estimate_token_count(msg.content)
            if tokens_used + msg_tokens <= self.max_context_tokens:
                trimmed_messages.insert(0, msg)
                tokens_used += msg_tokens
            else:
                logger.info(f"Trimmed message to fit context window: {msg.content[:50]}...")

        context.recent_messages = trimmed_messages
        context.context_window_tokens = tokens_used

        return context

    async def build_conversation_context(
        self,
        conversation_id: str,
        current_message: str,
        current_llm_client: Any = None,
    ) -> ConversationContext:
        """
        Build complete conversation context for the current message.

        Args:
            conversation_id: The conversation ID
            current_message: The current user message
            current_llm_client: LLM client for summarization (optional)

        Returns:
            Complete conversation context
        """
        # Fetch all conversation history
        all_messages = await self.fetch_conversation_history(conversation_id)

        if not all_messages:
            return ConversationContext(
                conversation_id=conversation_id,
                recent_messages=[],
                total_message_count=0,
            )

        total_count = len(all_messages)

        # Split into recent and older messages
        if total_count <= self.max_recent_messages:
            recent_messages = all_messages
            older_messages = []
        else:
            recent_messages = all_messages[-self.max_recent_messages :]
            older_messages = all_messages[: -self.max_recent_messages]

        # Summarize older messages if any
        summary = None
        if older_messages:
            summary = await self.summarize_conversation(older_messages, current_llm_client)

        # Detect conversation branch
        has_branch = self.detect_conversation_branch(current_message, recent_messages)

        # Calculate context window tokens
        context_tokens = self.calculate_context_window_tokens(recent_messages, summary)

        # Build context
        context = ConversationContext(
            conversation_id=conversation_id,
            recent_messages=recent_messages,
            summary=summary,
            total_message_count=total_count,
            context_window_tokens=context_tokens,
            has_conversation_branch=has_branch,
        )

        # Trim to fit token limits
        context = self.trim_context_to_fit(context)

        logger.info(
            f"Built context for {conversation_id}: "
            f"{len(recent_messages)} recent messages, "
            f"{total_count - len(recent_messages)} summarized, "
            f"{context_tokens} tokens"
        )

        return context

    def format_context_for_prompt(
        self,
        context: ConversationContext,
    ) -> str:
        """
        Format conversation context for injection into system prompt.

        Args:
            context: Conversation context

        Returns:
            Formatted context string
        """
        parts = []

        # Add summary if available
        if context.summary:
            parts.append(f"Conversation Summary:\n{context.summary.summary}")
            if context.summary.topics:
                parts.append(f"Topics: {', '.join(context.summary.topics)}")

        # Add recent messages
        if context.recent_messages:
            parts.append("\nRecent Conversation:")
            for turn in context.recent_messages:
                role_label = "User" if turn.role == MessageRole.USER else "Assistant"
                parts.append(f"{role_label}: {turn.content}")

        # Add branch warning if detected
        if context.has_conversation_branch:
            parts.append("\nNote: The user may have changed topics.")

        return "\n".join(parts)
