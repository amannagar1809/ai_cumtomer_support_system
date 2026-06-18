"""LangGraph state schema for conversation flow."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """State schema that passes through all LangGraph nodes."""

    # Input message
    message: str = Field(description="The user's input message")
    conversation_id: Optional[UUID] = Field(default=None, description="Conversation ID")
    user_id: Optional[UUID] = Field(default=None, description="User ID")
    channel: str = Field(default="web", description="Communication channel")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Channel-specific metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

    # Intermediate results from each node
    intermediate_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from each processing node",
    )

    # Language detection result
    detected_language: Optional[str] = Field(default=None, description="Detected language code")
    language_confidence: Optional[float] = Field(default=None, description="Language detection confidence")

    # Intent detection result
    detected_intent: Optional[str] = Field(default=None, description="Detected intent")
    intent_confidence: Optional[float] = Field(default=None, description="Intent detection confidence")
    intent_entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")

    # Knowledge search result
    search_results: list[dict[str, Any]] = Field(default_factory=list, description="Knowledge base search results")
    search_query: Optional[str] = Field(default=None, description="Query used for search")

    # Response generation result
    generated_response: Optional[str] = Field(default=None, description="Generated response")
    response_source: Optional[str] = Field(default=None, description="Source of response (AI/knowledge)")

    # Sentiment analysis result
    sentiment: Optional[str] = Field(default=None, description="Detected sentiment (positive/negative/neutral)")
    sentiment_score: Optional[float] = Field(default=None, description="Sentiment score (-1 to 1)")

    # Escalation decision result
    should_escalate: bool = Field(default=False, description="Whether to escalate to human")
    escalation_reason: Optional[str] = Field(default=None, description="Reason for escalation")

    # Final response
    final_response: Optional[str] = Field(default=None, description="Final response to return to user")
    response_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the final response",
    )

    # Error handling
    error: Optional[str] = Field(default=None, description="Error message if processing failed")
    failed_node: Optional[str] = Field(default=None, description="Node where failure occurred")

    # Execution tracking
    current_node: Optional[str] = Field(default=None, description="Current node being executed")
    execution_path: list[str] = Field(default_factory=list, description="Path of executed nodes")
    node_durations: dict[str, float] = Field(
        default_factory=dict,
        description="Duration of each node execution in seconds",
    )

    # Checkpoint for resumption
    checkpoint_id: Optional[str] = Field(default=None, description="Checkpoint ID for resumption")
    can_resume: bool = Field(default=False, description="Whether execution can be resumed from checkpoint")

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
