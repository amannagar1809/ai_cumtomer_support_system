"""Intent classification system for customer queries."""

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.services.langgraph.intent_training_data import get_all_training_examples

logger = logging.getLogger(__name__)

# Confidence threshold for classification
CONFIDENCE_THRESHOLD = 0.70


class IntentClass(str, Enum):
    """Intent classes with clear boundaries."""

    PRODUCT_QUERY = "product_query"
    TECHNICAL_ISSUE = "technical_issue"
    BILLING_ISSUE = "billing_issue"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"
    UNKNOWN = "unknown"

    def get_description(self) -> str:
        """Get description of the intent class."""
        descriptions = {
            self.PRODUCT_QUERY: "Questions about products, features, specifications, pricing, availability",
            self.TECHNICAL_ISSUE: "Technical problems, bugs, errors, installation issues, configuration problems",
            self.BILLING_ISSUE: "Questions about invoices, payments, subscriptions, billing disputes",
            self.REFUND_REQUEST: "Requests for refunds, returns, cancellations",
            self.COMPLAINT: "Negative feedback, service complaints, dissatisfaction expressions",
            self.GENERAL_INQUIRY: "General questions, greetings, feedback, miscellaneous queries",
            self.UNKNOWN: "Low confidence or unclear intent",
        }
        return descriptions.get(self, "Unknown intent")


# Intent routing table - maps intents to processing nodes
INTENT_ROUTING_TABLE = {
    IntentClass.PRODUCT_QUERY: "knowledge_search",
    IntentClass.TECHNICAL_ISSUE: "knowledge_search",
    IntentClass.BILLING_ISSUE: "knowledge_search",
    IntentClass.REFUND_REQUEST: "escalation_decision",
    IntentClass.COMPLAINT: "escalation_decision",
    IntentClass.GENERAL_INQUIRY: "knowledge_search",
    IntentClass.UNKNOWN: "knowledge_search",
}


class IntentClassificationResult(BaseModel):
    """Result of intent classification."""

    intent: IntentClass = Field(description="Classified intent")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    is_confident: bool = Field(description="Whether confidence meets threshold")
    routing_node: str = Field(description="Next node to route to based on intent")
    reasoning: Optional[str] = Field(default=None, description="Reasoning for classification")


class IntentClassifier:
    """Intent classifier using few-shot prompting."""

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        """
        Initialize the intent classifier.

        Args:
            confidence_threshold: Minimum confidence for classification (default 0.70)
        """
        self.confidence_threshold = confidence_threshold
        self._load_training_examples()

    def _load_training_examples(self) -> None:
        """Load training examples for few-shot prompting."""
        all_examples = get_all_training_examples()
        self.product_query_examples = all_examples.get("product_query", [])
        self.technical_issue_examples = all_examples.get("technical_issue", [])
        self.billing_issue_examples = all_examples.get("billing_issue", [])
        self.refund_request_examples = all_examples.get("refund_request", [])
        self.complaint_examples = all_examples.get("complaint", [])
        self.general_inquiry_examples = all_examples.get("general_inquiry", [])

    def _calculate_similarity(self, message: str, examples: list[str]) -> float:
        """
        Calculate similarity between message and example set using keyword matching.

        Args:
            message: The message to classify
            examples: List of example messages for an intent

        Returns:
            Similarity score (0.0 to 1.0)
        """
        message_lower = message.lower()
        message_words = set(message_lower.split())

        total_similarity = 0.0
        for example in examples:
            example_lower = example.lower()
            example_words = set(example_lower.split())

            # Calculate word overlap
            if not message_words or not example_words:
                continue

            overlap = len(message_words & example_words)
            union = len(message_words | example_words)
            similarity = overlap / union if union > 0 else 0.0
            total_similarity += similarity

        # Average similarity across all examples
        avg_similarity = total_similarity / len(examples) if examples else 0.0
        return avg_similarity

    def classify(self, message: str) -> IntentClassificationResult:
        """
        Classify the intent of a message.

        Args:
            message: The message to classify

        Returns:
            IntentClassificationResult with intent, confidence, and routing info
        """
        # Calculate similarity for each intent class
        similarities = {
            IntentClass.PRODUCT_QUERY: self._calculate_similarity(message, self.product_query_examples),
            IntentClass.TECHNICAL_ISSUE: self._calculate_similarity(message, self.technical_issue_examples),
            IntentClass.BILLING_ISSUE: self._calculate_similarity(message, self.billing_issue_examples),
            IntentClass.REFUND_REQUEST: self._calculate_similarity(message, self.refund_request_examples),
            IntentClass.COMPLAINT: self._calculate_similarity(message, self.complaint_examples),
            IntentClass.GENERAL_INQUIRY: self._calculate_similarity(message, self.general_inquiry_examples),
        }

        # Find the intent with highest similarity
        best_intent = max(similarities, key=similarities.get)
        best_confidence = similarities[best_intent]

        # Apply confidence threshold
        if best_confidence < self.confidence_threshold:
            best_intent = IntentClass.UNKNOWN
            best_confidence = best_confidence
            reasoning = f"Confidence {best_confidence:.2f} below threshold {self.confidence_threshold}"
        else:
            reasoning = f"Best match with {best_confidence:.2f} confidence"

        # Get routing node
        routing_node = INTENT_ROUTING_TABLE.get(best_intent, "knowledge_search")

        result = IntentClassificationResult(
            intent=best_intent,
            confidence=best_confidence,
            is_confident=best_confidence >= self.confidence_threshold,
            routing_node=routing_node,
            reasoning=reasoning,
        )

        logger.info(
            f"Classified message as {best_intent.value} "
            f"(confidence: {best_confidence:.2f}, routing: {routing_node})"
        )

        return result

    def get_intent_statistics(self, message: str) -> dict[str, float]:
        """
        Get similarity scores for all intent classes.

        Args:
            message: The message to analyze

        Returns:
            Dictionary mapping intent classes to similarity scores
        """
        similarities = {
            IntentClass.PRODUCT_QUERY: self._calculate_similarity(message, self.product_query_examples),
            IntentClass.TECHNICAL_ISSUE: self._calculate_similarity(message, self.technical_issue_examples),
            IntentClass.BILLING_ISSUE: self._calculate_similarity(message, self.billing_issue_examples),
            IntentClass.REFUND_REQUEST: self._calculate_similarity(message, self.refund_request_examples),
            IntentClass.COMPLAINT: self._calculate_similarity(message, self.complaint_examples),
            IntentClass.GENERAL_INQUIRY: self._calculate_similarity(message, self.general_inquiry_examples),
        }

        return {intent.value: score for intent, score in similarities.items()}
