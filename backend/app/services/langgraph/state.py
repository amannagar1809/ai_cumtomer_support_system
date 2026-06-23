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

    # Message type and validation
    message_type: str = Field(default="text", description="Message type (text, image, file, voice)")
    is_duplicate: bool = Field(default=False, description="Whether this message is a duplicate")
    message_hash: Optional[str] = Field(default=None, description="Hash for duplicate detection")
    queue_priority: int = Field(default=5, description="Queue priority (1-10, higher is more urgent)")

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
    intent_sub_intent: Optional[str] = Field(default=None, description="Detected sub-intent")
    intent_entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    intent_routing_node: Optional[str] = Field(default=None, description="Next node to route to based on intent")
    intent_is_confident: bool = Field(default=False, description="Whether intent confidence meets threshold")
    intent_classification_id: Optional[str] = Field(default=None, description="Unique classification ID for analytics")
    intent_model_variant: Optional[str] = Field(default=None, description="A/B test model variant used")

    # Conversation context
    conversation_history: list[dict[str, Any]] = Field(default_factory=list, description="Recent conversation history")
    conversation_summary: Optional[str] = Field(default=None, description="Summary of older conversation messages")
    conversation_topics: list[str] = Field(default_factory=list, description="Key topics discussed in conversation")
    conversation_entities: dict[str, Any] = Field(default_factory=dict, description="Entities mentioned in conversation")
    has_conversation_branch: bool = Field(default=False, description="Whether conversation branch detected")
    context_window_tokens: int = Field(default=0, description="Estimated token count of context window")
    total_message_count: int = Field(default=0, description="Total messages in conversation")

    # Customer profile context
    customer_profile: dict[str, Any] = Field(default_factory=dict, description="Customer profile information")
    customer_tier: Optional[str] = Field(default=None, description="Customer tier (regular/premium/vip)")
    customer_is_vip: bool = Field(default=False, description="Whether customer is VIP")
    customer_join_date: Optional[str] = Field(default=None, description="Customer join date")
    customer_language: Optional[str] = Field(default=None, description="Customer preferred language")
    past_tickets: list[dict[str, Any]] = Field(default_factory=list, description="Past tickets")
    crm_data: dict[str, Any] = Field(default_factory=dict, description="Additional CRM data")
    is_priority_customer: bool = Field(default=False, description="Whether customer gets priority handling")

    # Knowledge search result
    search_results: list[dict[str, Any]] = Field(default_factory=list, description="Knowledge base search results")
    search_query: Optional[str] = Field(default=None, description="Query used for search")

    # Response generation result
    generated_response: Optional[str] = Field(default=None, description="Generated response")
    response_source: Optional[str] = Field(default=None, description="Source of response (AI/knowledge)")

    # Sentiment analysis result
    sentiment: Optional[str] = Field(default=None, description="Detected sentiment (positive/negative/neutral)")
    sentiment_score: Optional[float] = Field(default=None, description="Sentiment score (-1 to 1)")
    sentiment_class: Optional[str] = Field(default=None, description="Detailed sentiment class (positive/neutral/negative/angry/frustrated/urgent)")
    sentiment_scores: dict[str, float] = Field(default_factory=dict, description="Scores for all sentiment classes")
    sentiment_confidence: Optional[float] = Field(default=None, description="Sentiment confidence score (0-1)")
    sentiment_trend: Optional[str] = Field(default=None, description="Sentiment trend (escalating/de_escalating/stable)")
    sentiment_history: list[dict[str, Any]] = Field(default_factory=list, description="Sentiment history for trend analysis")
    sentiment_analysis_id: Optional[str] = Field(default=None, description="Unique sentiment analysis ID")
    sentiment_latency_ms: Optional[float] = Field(default=None, description="Sentiment analysis latency in milliseconds")
    sentiment_language: Optional[str] = Field(default=None, description="Language used for sentiment analysis")
    sentiment_model_used: Optional[str] = Field(default=None, description="Model used for sentiment analysis")
    sentiment_is_fallback: bool = Field(default=False, description="Whether fallback model was used")
    sentiment_f1_score: Optional[float] = Field(default=None, description="Model F1 score for this language")

    # Angry customer handling
    is_angry_customer: bool = Field(default=False, description="Whether customer is angry")
    angry_score: float = Field(default=0.0, description="Angry sentiment score")
    angry_customer_flag: dict[str, Any] = Field(default_factory=dict, description="Dashboard flag details")
    angry_customer_actions: list[str] = Field(default_factory=list, description="Actions taken for angry customer")
    angry_customer_notifications: list[dict[str, Any]] = Field(default_factory=list, description="Supervisor notifications sent")
    ticket_sentiment_tag: Optional[str] = Field(default=None, description="Sentiment tag for ticket creation")
    workflow_optimized: bool = Field(default=False, description="Whether workflow was optimized for speed")

    # Ticket detection
    should_create_ticket: bool = Field(default=False, description="Whether to create a ticket")
    ticket_triggers: list[dict[str, Any]] = Field(default_factory=list, description="Triggers detected for ticket creation")
    ticket_decision: Optional[str] = Field(default=None, description="Ticket creation decision (create/cancelled/deferred/skip)")
    ticket_cooldown_active: bool = Field(default=False, description="Whether ticket cooldown is active")
    ticket_user_cancelled: bool = Field(default=False, description="Whether user cancelled ticket creation")
    ticket_audit_log: dict[str, Any] = Field(default_factory=dict, description="Audit log for ticket decision")

    # Ticket extraction
    extracted_ticket_data: dict[str, Any] = Field(default_factory=dict, description="Extracted ticket data")
    ticket_extraction_id: Optional[str] = Field(default=None, description="Unique ticket extraction ID")
    ticket_extraction_confidence: Optional[float] = Field(default=None, description="Extraction confidence score")
    ticket_extraction_valid: bool = Field(default=True, description="Whether extracted data is valid")
    ticket_extraction_errors: list[str] = Field(default_factory=list, description="Validation errors")
    ticket_needs_human_review: bool = Field(default=False, description="Whether ticket needs human review")
    ticket_human_edited: bool = Field(default=False, description="Whether ticket was edited by human")

    # Pending tickets queue
    pending_ticket_id: Optional[str] = Field(default=None, description="Pending ticket ID")
    pending_ticket_status: Optional[str] = Field(default=None, description="Pending ticket status (pending/approved/rejected)")
    pending_ticket_created: bool = Field(default=False, description="Whether ticket was added to pending queue")

    # Priority detection
    detected_priority: Optional[str] = Field(default=None, description="Detected ticket priority")
    original_priority: Optional[str] = Field(default=None, description="Priority before adjustments")
    priority_reasons: list[str] = Field(default_factory=list, description="Reasons for priority assignment")
    priority_score: Optional[float] = Field(default=None, description="Priority score")
    priority_vip_adjusted: bool = Field(default=False, description="Whether priority was adjusted for VIP")
    priority_sla_escalated: bool = Field(default=False, description="Whether priority was escalated due to SLA")
    priority_override_applied: bool = Field(default=False, description="Whether override rule was applied")

    # CRM integration
    crm_contact_id: Optional[str] = Field(default=None, description="CRM contact ID")
    crm_account_id: Optional[str] = Field(default=None, description="CRM account ID")
    crm_data_synced: bool = Field(default=False, description="Whether CRM data was synced")
    crm_sync_timestamp: Optional[str] = Field(default=None, description="CRM sync timestamp")
    crm_quota_remaining: Optional[int] = Field(default=None, description="CRM API quota remaining")
    crm_rate_limited: bool = Field(default=False, description="Whether CRM request was rate limited")

    # Purchase history
    purchase_history_summary: dict[str, Any] = Field(default_factory=dict, description="Purchase history summary")
    total_transactions: Optional[int] = Field(default=None, description="Total number of transactions")
    total_customer_value: Optional[float] = Field(default=None, description="Total customer value")
    failed_payment_count: Optional[int] = Field(default=None, description="Number of failed payments")
    subscription_count: Optional[int] = Field(default=None, description="Number of subscription purchases")
    one_time_count: Optional[int] = Field(default=None, description="Number of one-time purchases")

    # CRM open tickets
    crm_open_tickets: list[dict[str, Any]] = Field(default_factory=list, description="Open tickets from CRM")
    crm_total_tickets: Optional[int] = Field(default=None, description="Total number of CRM tickets")
    crm_open_tickets_count: Optional[int] = Field(default=None, description="Number of open CRM tickets")
    crm_high_priority_tickets: Optional[int] = Field(default=None, description="Number of high priority CRM tickets")
    crm_existing_ticket_message: Optional[str] = Field(default=None, description="Message about existing tickets")
    crm_duplicate_ticket_detected: bool = Field(default=False, description="Whether duplicate ticket was detected")

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
