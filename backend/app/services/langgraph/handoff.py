"""Handoff service for packaging conversation context for human agents."""

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageEntry(BaseModel):
    """Single message entry in conversation transcript."""

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(description="Message timestamp")
    sentiment: Optional[str] = Field(default=None, description="Sentiment analysis result")
    confidence: Optional[float] = Field(default=None, description="AI confidence for assistant messages")


class SentimentTimeline(BaseModel):
    """Sentiment timeline for the conversation."""

    message_index: int = Field(description="Message index in conversation")
    sentiment: str = Field(description="Sentiment value (negative, neutral, positive)")
    score: float = Field(description="Sentiment score")
    timestamp: datetime = Field(description="Timestamp of sentiment analysis")


class TicketDetails(BaseModel):
    """Ticket details if a ticket was created."""

    ticket_id: Optional[str] = Field(default=None, description="Ticket ID if created")
    status: Optional[str] = Field(default=None, description="Ticket status")
    priority: Optional[str] = Field(default=None, description="Ticket priority")
    category: Optional[str] = Field(default=None, description="Ticket category")
    created_at: Optional[datetime] = Field(default=None, description="Ticket creation timestamp")
    summary: Optional[str] = Field(default=None, description="Ticket summary")


class CustomerProfile(BaseModel):
    """Customer profile information."""

    customer_id: Optional[str] = Field(default=None, description="Customer ID")
    name: Optional[str] = Field(default=None, description="Customer name")
    email: Optional[str] = Field(default=None, description="Customer email")
    phone: Optional[str] = Field(default=None, description="Customer phone")
    customer_type: Optional[str] = Field(default=None, description="Customer type (regular, premium, vip, enterprise)")
    tier: Optional[str] = Field(default=None, description="Customer tier")
    is_vip: bool = Field(default=False, description="Whether customer is VIP")
    join_date: Optional[datetime] = Field(default=None, description="Customer join date")
    language: Optional[str] = Field(default=None, description="Customer preferred language")


class CustomerHistory(BaseModel):
    """Customer history information."""

    total_conversations: int = Field(default=0, description="Total number of conversations")
    total_tickets: int = Field(default=0, description="Total number of tickets")
    open_tickets: int = Field(default=0, description="Number of open tickets")
    last_contact: Optional[datetime] = Field(default=None, description="Last contact date")
    average_sentiment: Optional[str] = Field(default=None, description="Average sentiment across conversations")


class AISuggestedSolution(BaseModel):
    """AI-suggested solution for the agent."""

    suggested_response: str = Field(description="AI's suggested response")
    confidence: float = Field(description="AI confidence in the suggestion")
    reasoning: Optional[str] = Field(default=None, description="AI's reasoning for the suggestion")
    alternative_solutions: list[str] = Field(default_factory=list, description="Alternative solutions suggested by AI")
    knowledge_base_articles: list[str] = Field(default_factory=list, description="Relevant knowledge base articles")


class HandoffData(BaseModel):
    """Complete handoff data package for human agent."""

    conversation_id: str = Field(description="Conversation ID for seamless transition")
    handoff_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Handoff timestamp")
    escalation_reason: Optional[str] = Field(default=None, description="Reason for escalation")
    
    # Conversation context
    transcript: list[MessageEntry] = Field(default_factory=list, description="Full conversation transcript")
    sentiment_timeline: list[SentimentTimeline] = Field(default_factory=list, description="Sentiment timeline per message")
    
    # Ticket information
    ticket_details: Optional[TicketDetails] = Field(default=None, description="Ticket details if created")
    
    # Customer information
    customer_profile: Optional[CustomerProfile] = Field(default=None, description="Customer profile")
    customer_history: Optional[CustomerHistory] = Field(default=None, description="Customer history")
    
    # AI context
    ai_attempted_responses: list[str] = Field(default_factory=list, description="AI attempted responses")
    ai_suggested_solution: Optional[AISuggestedSolution] = Field(default=None, description="AI-suggested solution")
    
    # Escalation context
    escalation_payload: dict[str, Any] = Field(default_factory=dict, description="Escalation payload with metadata")
    agent_team: Optional[str] = Field(default=None, description="Target agent team for routing")
    is_vip: bool = Field(default=False, description="Whether customer is VIP")
    
    # Additional context
    intent: Optional[str] = Field(default=None, description="Detected intent")
    topics: list[str] = Field(default_factory=list, description="Detected topics")
    entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")


class HandoffService:
    """Service for packaging handoff data for human agents."""

    def __init__(self):
        """Initialize handoff service."""
        self.logger = logger

    def prepare_handoff(
        self,
        conversation_id: str,
        escalation_reason: Optional[str],
        state: dict[str, Any],
    ) -> HandoffData:
        """
        Prepare complete handoff data package.

        Args:
            conversation_id: Conversation ID
            escalation_reason: Reason for escalation
            state: Current conversation state

        Returns:
            Complete handoff data package
        """
        self.logger.info(f"Preparing handoff data for conversation {conversation_id}")

        # Build transcript from conversation history
        transcript = self._build_transcript(state)

        # Build sentiment timeline
        sentiment_timeline = self._build_sentiment_timeline(state)

        # Extract ticket details
        ticket_details = self._extract_ticket_details(state)

        # Extract customer profile
        customer_profile = self._extract_customer_profile(state)

        # Extract customer history
        customer_history = self._extract_customer_history(state)

        # Extract AI attempted responses
        ai_attempted_responses = self._extract_ai_responses(state)

        # Build AI suggested solution
        ai_suggested_solution = self._build_ai_suggested_solution(state)

        # Extract escalation payload
        escalation_payload = state.get("escalation_payload", {})
        agent_team = escalation_payload.get("agent_team", "general")
        is_vip = escalation_payload.get("is_vip", False)

        # Build handoff data
        handoff_data = HandoffData(
            conversation_id=conversation_id,
            escalation_reason=escalation_reason,
            transcript=transcript,
            sentiment_timeline=sentiment_timeline,
            ticket_details=ticket_details,
            customer_profile=customer_profile,
            customer_history=customer_history,
            ai_attempted_responses=ai_attempted_responses,
            ai_suggested_solution=ai_suggested_solution,
            escalation_payload=escalation_payload,
            agent_team=agent_team,
            is_vip=is_vip,
            intent=state.get("intent"),
            topics=state.get("topics", []),
            entities=state.get("entities", {}),
        )

        self.logger.info(f"Handoff data prepared with {len(transcript)} messages")
        return handoff_data

    def _build_transcript(self, state: dict[str, Any]) -> list[MessageEntry]:
        """
        Build conversation transcript from state.

        Args:
            state: Current conversation state

        Returns:
            List of message entries
        """
        transcript = []
        
        # Extract conversation history from state
        conversation_history = state.get("context", {}).get("history", [])
        
        for i, message in enumerate(conversation_history):
            entry = MessageEntry(
                role=message.get("role", "unknown"),
                content=message.get("content", ""),
                timestamp=message.get("timestamp", datetime.now(UTC)),
                sentiment=message.get("sentiment"),
                confidence=message.get("confidence"),
            )
            transcript.append(entry)
        
        # Add current message if not in history
        current_message = state.get("current_message")
        if current_message:
            entry = MessageEntry(
                role="user",
                content=current_message,
                timestamp=datetime.now(UTC),
                sentiment=state.get("sentiment"),
            )
            transcript.append(entry)
        
        return transcript

    def _build_sentiment_timeline(self, state: dict[str, Any]) -> list[SentimentTimeline]:
        """
        Build sentiment timeline from state.

        Args:
            state: Current conversation state

        Returns:
            List of sentiment timeline entries
        """
        timeline = []
        
        # Extract sentiment history from state
        sentiment_history = state.get("sentiment_history", [])
        
        for i, sentiment_data in enumerate(sentiment_history):
            entry = SentimentTimeline(
                message_index=i,
                sentiment=sentiment_data.get("sentiment", "neutral"),
                score=sentiment_data.get("score", 0.0),
                timestamp=sentiment_data.get("timestamp", datetime.now(UTC)),
            )
            timeline.append(entry)
        
        # Add current sentiment
        current_sentiment = state.get("sentiment")
        if current_sentiment:
            entry = SentimentTimeline(
                message_index=len(timeline),
                sentiment=current_sentiment,
                score=state.get("sentiment_score", 0.0),
                timestamp=datetime.now(UTC),
            )
            timeline.append(entry)
        
        return timeline

    def _extract_ticket_details(self, state: dict[str, Any]) -> Optional[TicketDetails]:
        """
        Extract ticket details from state.

        Args:
            state: Current conversation state

        Returns:
            Ticket details if available
        """
        ticket_data = state.get("ticket")
        
        if not ticket_data:
            return None
        
        return TicketDetails(
            ticket_id=ticket_data.get("id"),
            status=ticket_data.get("status"),
            priority=ticket_data.get("priority"),
            category=ticket_data.get("category"),
            created_at=ticket_data.get("created_at"),
            summary=ticket_data.get("summary"),
        )

    def _extract_customer_profile(self, state: dict[str, Any]) -> Optional[CustomerProfile]:
        """
        Extract customer profile from state.

        Args:
            state: Current conversation state

        Returns:
            Customer profile if available
        """
        customer_profile = state.get("customer_profile", {})
        customer_context = state.get("context", {}).get("customer", {})
        
        return CustomerProfile(
            customer_id=state.get("user_id"),
            name=customer_profile.get("name") or customer_context.get("name"),
            email=customer_profile.get("email") or customer_context.get("email"),
            phone=customer_profile.get("phone") or customer_context.get("phone"),
            customer_type=customer_profile.get("customer_type"),
            tier=state.get("customer_tier"),
            is_vip=state.get("customer_is_vip", False),
            join_date=customer_profile.get("join_date"),
            language=customer_profile.get("language"),
        )

    def _extract_customer_history(self, state: dict[str, Any]) -> Optional[CustomerHistory]:
        """
        Extract customer history from state.

        Args:
            state: Current conversation state

        Returns:
            Customer history if available
        """
        customer_context = state.get("context", {}).get("customer", {})
        
        return CustomerHistory(
            total_conversations=customer_context.get("total_conversations", 0),
            total_tickets=customer_context.get("total_tickets", 0),
            open_tickets=customer_context.get("open_tickets", 0),
            last_contact=customer_context.get("last_contact"),
            average_sentiment=customer_context.get("average_sentiment"),
        )

    def _extract_ai_responses(self, state: dict[str, Any]) -> list[str]:
        """
        Extract AI attempted responses from state.

        Args:
            state: Current conversation state

        Returns:
            List of AI attempted responses
        """
        ai_responses = []
        
        # Extract from conversation history
        conversation_history = state.get("context", {}).get("history", [])
        for message in conversation_history:
            if message.get("role") == "assistant":
                ai_responses.append(message.get("content", ""))
        
        # Extract from state
        final_response = state.get("final_response")
        if final_response:
            ai_responses.append(final_response)
        
        return ai_responses

    def _build_ai_suggested_solution(self, state: dict[str, Any]) -> Optional[AISuggestedSolution]:
        """
        Build AI suggested solution from state.

        Args:
            state: Current conversation state

        Returns:
            AI suggested solution if available
        """
        final_response = state.get("final_response")
        if not final_response:
            return None
        
        confidence = state.get("ai_confidence", 0.0)
        
        return AISuggestedSolution(
            suggested_response=final_response,
            confidence=confidence,
            reasoning=state.get("response_metadata", {}).get("reasoning"),
            alternative_solutions=state.get("response_metadata", {}).get("alternatives", []),
            knowledge_base_articles=state.get("response_metadata", {}).get("kb_articles", []),
        )

    def get_transfer_message(self, is_vip: bool = False) -> str:
        """
        Get transfer message for customer.

        Args:
            is_vip: Whether customer is VIP

        Returns:
            Transfer message
        """
        if is_vip:
            return "I'm connecting you with our dedicated VIP support team right away. They'll have all the context of our conversation."
        else:
            return "I'm transferring you to a human agent who can help you better. They'll have all the context of our conversation."
