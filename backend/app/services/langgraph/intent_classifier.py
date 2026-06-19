"""Intent classification system for customer queries."""

import logging
import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.services.langgraph.intent_training_data import get_all_training_examples

logger = logging.getLogger(__name__)

# Confidence threshold for classification
CONFIDENCE_THRESHOLD = 0.70

# A/B testing configuration
AB_TEST_ENABLED = True
AB_TEST_VARIANT_A = "keyword_similarity"  # Current implementation
AB_TEST_VARIANT_B = "enhanced_similarity"  # Future implementation
AB_TEST_SPLIT_RATIO = 0.5  # 50% to each variant


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


class SubIntentClass(str, Enum):
    """Sub-intent classes for more granular classification."""

    # Product Query sub-intents
    PRODUCT_FEATURES = "product_features"
    PRODUCT_PRICING = "product_pricing"
    PRODUCT_AVAILABILITY = "product_availability"
    PRODUCT_COMPARISON = "product_comparison"
    PRODUCT_INTEGRATIONS = "product_integrations"
    PRODUCT_REQUIREMENTS = "product_requirements"

    # Technical Issue sub-intents
    TECH_ERROR = "tech_error"
    TECH_INSTALLATION = "tech_installation"
    TECH_CONFIGURATION = "tech_configuration"
    TECH_PERFORMANCE = "tech_performance"
    TECH_AUTHENTICATION = "tech_authentication"
    TECH_API = "tech_api"

    # Billing Issue sub-intents
    BILLING_PAYMENT_FAILED = "billing_payment_failed"
    BILLING_INVOICE = "billing_invoice"
    BILLING_SUBSCRIPTION = "billing_subscription"
    BILLING_REFUND = "billing_refund"
    BILLING_UPDATE = "billing_update"
    BILLING_DISPUTE = "billing_dispute"

    # Refund Request sub-intents
    REFUND_FULL = "refund_full"
    REFUND_PARTIAL = "refund_partial"
    REFUND_CANCELLATION = "refund_cancellation"
    REFUND_RETURN = "refund_return"
    REFUND_DISPUTE = "refund_dispute"

    # Complaint sub-intents
    COMPLAINT_SERVICE = "complaint_service"
    COMPLAINT_PRODUCT = "complaint_product"
    COMPLAINT_SUPPORT = "complaint_support"
    COMPLAINT_BILLING = "complaint_billing"
    COMPLAINT_DELAY = "complaint_delay"

    # General Inquiry sub-intents
    GENERAL_GREETING = "general_greeting"
    GENERAL_QUESTION = "general_question"
    GENERAL_FEEDBACK = "general_feedback"
    GENERAL_INFO = "general_info"

    UNKNOWN = None


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
    """Structured JSON output for intent classification."""

    intent: str = Field(description="Classified intent")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    sub_intent: Optional[str] = Field(default=None, description="Sub-intent classification")
    entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    is_confident: bool = Field(description="Whether confidence meets threshold")
    routing_node: str = Field(description="Next node to route to based on intent")
    reasoning: Optional[str] = Field(default=None, description="Reasoning for classification")
    model_variant: Optional[str] = Field(default=None, description="A/B test model variant used")
    classification_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique classification ID")

    def to_json(self) -> dict[str, Any]:
        """Convert to structured JSON format for downstream nodes."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "sub_intent": self.sub_intent,
            "entities": self.entities,
        }


class IntentClassifier:
    """Intent classifier using few-shot prompting with entity extraction and A/B testing."""

    def __init__(
        self,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        is_vip_user: bool = False,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the intent classifier.

        Args:
            confidence_threshold: Minimum confidence for classification (default 0.70)
            is_vip_user: Whether the user is a VIP customer (for intent override)
            user_id: User ID for A/B test assignment and logging
        """
        self.confidence_threshold = confidence_threshold
        self.is_vip_user = is_vip_user
        self.user_id = user_id
        self._load_training_examples()
        self._assign_ab_test_variant()

    def _load_training_examples(self) -> None:
        """Load training examples for few-shot prompting."""
        all_examples = get_all_training_examples()
        self.product_query_examples = all_examples.get("product_query", [])
        self.technical_issue_examples = all_examples.get("technical_issue", [])
        self.billing_issue_examples = all_examples.get("billing_issue", [])
        self.refund_request_examples = all_examples.get("refund_request", [])
        self.complaint_examples = all_examples.get("complaint", [])
        self.general_inquiry_examples = all_examples.get("general_inquiry", [])

    def _assign_ab_test_variant(self) -> None:
        """Assign A/B test variant based on user ID hash."""
        if not AB_TEST_ENABLED or not self.user_id:
            self.model_variant = AB_TEST_VARIANT_A
            return

        # Use hash of user_id to consistently assign variant
        user_hash = hash(self.user_id) % 100
        if user_hash < (AB_TEST_SPLIT_RATIO * 100):
            self.model_variant = AB_TEST_VARIANT_A
        else:
            self.model_variant = AB_TEST_VARIANT_B

    def _extract_entities(self, message: str, intent: IntentClass) -> dict[str, Any]:
        """
        Extract entities relevant to each intent type.

        Args:
            message: The message to extract entities from
            intent: The classified intent

        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        message_lower = message.lower()

        # Common entity patterns
        # Extract amounts (currency)
        amount_pattern = r'\$[\d,]+\.?\d*|[\d,]+\.?\d*\s*(?:usd|dollars?|cents?)'
        amounts = re.findall(amount_pattern, message_lower, re.IGNORECASE)
        if amounts:
            entities["amount"] = amounts[0]

        # Extract dates
        date_pattern = r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}'
        dates = re.findall(date_pattern, message_lower, re.IGNORECASE)
        if dates:
            entities["date"] = dates[0]

        # Extract order numbers
        order_pattern = r'order\s*#?(\d+)|invoice\s*#?(\d+)|ticket\s*#?(\d+)'
        order_match = re.search(order_pattern, message_lower)
        if order_match:
            entities["order_id"] = order_match.group(1) or order_match.group(2) or order_match.group(3)

        # Intent-specific entity extraction
        if intent == IntentClass.PRODUCT_QUERY:
            # Extract product names
            product_keywords = ["product", "plan", "subscription", "service", "software", "app"]
            for keyword in product_keywords:
                if keyword in message_lower:
                    # Try to extract product name after the keyword
                    pattern = rf'{keyword}\s+(?:the\s+)?(\w+(?:\s+\w+)?)'
                    product_match = re.search(pattern, message_lower)
                    if product_match:
                        entities["product_name"] = product_match.group(1)
                        break

            # Extract plan names
            plan_pattern = r'(?:basic|pro|premium|enterprise|starter|free|trial)\s*(?:plan|tier|subscription)?'
            plan_match = re.search(plan_pattern, message_lower)
            if plan_match:
                entities["plan_name"] = plan_match.group(0)

        elif intent == IntentClass.TECHNICAL_ISSUE:
            # Extract error codes
            error_code_pattern = r'(?:error|code|status)\s*[:#]?\s*(\d{3,4}|[a-z]{2,}-\d+|[a-z]+_\d+)'
            error_match = re.search(error_code_pattern, message_lower, re.IGNORECASE)
            if error_match:
                entities["error_code"] = error_match.group(1)

            # Extract HTTP status codes
            http_pattern = r'(?:http\s*)?(\d{3})\s*(?:error)?'
            http_match = re.search(http_pattern, message_lower)
            if http_match:
                entities["http_status"] = http_match.group(1)

            # Extract device/platform info
            device_pattern = r'(?:windows|mac|linux|android|ios|iphone|ipad|chrome|firefox|safari|edge)'
            device_match = re.search(device_pattern, message_lower, re.IGNORECASE)
            if device_match:
                entities["device"] = device_match.group(0)

        elif intent == IntentClass.BILLING_ISSUE:
            # Extract payment methods
            payment_pattern = r'(?:credit\s*card|debit\s*card|paypal|bank\s*transfer|stripe|ach|check)'
            payment_match = re.search(payment_pattern, message_lower, re.IGNORECASE)
            if payment_match:
                entities["payment_method"] = payment_match.group(0)

            # Extract billing cycle
            cycle_pattern = r'(?:monthly|annual|yearly|quarterly|weekly|daily)\s*(?:billing|subscription|payment)?'
            cycle_match = re.search(cycle_pattern, message_lower, re.IGNORECASE)
            if cycle_match:
                entities["billing_cycle"] = cycle_match.group(0)

        elif intent == IntentClass.REFUND_REQUEST:
            # Extract refund type
            refund_pattern = r'(?:full|partial|prorated)\s*(?:refund)?'
            refund_match = re.search(refund_pattern, message_lower, re.IGNORECASE)
            if refund_match:
                entities["refund_type"] = refund_match.group(0)

        elif intent == IntentClass.COMPLAINT:
            # Extract sentiment keywords
            negative_keywords = ["terrible", "awful", "horrible", "worst", "disappointed", "frustrated", "angry"]
            found_keywords = [kw for kw in negative_keywords if kw in message_lower]
            if found_keywords:
                entities["sentiment_keywords"] = found_keywords

        return entities

    def _classify_sub_intent(self, message: str, intent: IntentClass) -> Optional[str]:
        """
        Classify sub-intent based on the main intent and message content.

        Args:
            message: The message to classify
            intent: The main classified intent

        Returns:
            Sub-intent classification or None
        """
        message_lower = message.lower()

        # Sub-intent classification rules
        if intent == IntentClass.PRODUCT_QUERY:
            if any(word in message_lower for word in ["feature", "functionality", "capability"]):
                return SubIntentClass.PRODUCT_FEATURES.value
            elif any(word in message_lower for word in ["price", "cost", "pricing", "how much", "expensive"]):
                return SubIntentClass.PRODUCT_PRICING.value
            elif any(word in message_lower for word in ["available", "stock", "in stock", "out of stock"]):
                return SubIntentClass.PRODUCT_AVAILABILITY.value
            elif any(word in message_lower for word in ["compare", "difference", "versus", "vs"]):
                return SubIntentClass.PRODUCT_COMPARISON.value
            elif any(word in message_lower for word in ["integrate", "integration", "connect", "api"]):
                return SubIntentClass.PRODUCT_INTEGRATIONS.value
            elif any(word in message_lower for word in ["require", "need", "system", "hardware", "compatible"]):
                return SubIntentClass.PRODUCT_REQUIREMENTS.value

        elif intent == IntentClass.TECHNICAL_ISSUE:
            if any(word in message_lower for word in ["error", "bug", "fail", "crash", "exception"]):
                return SubIntentClass.TECH_ERROR.value
            elif any(word in message_lower for word in ["install", "setup", "deploy", "configure"]):
                return SubIntentClass.TECH_INSTALLATION.value
            elif any(word in message_lower for word in ["config", "setting", "preference", "option"]):
                return SubIntentClass.TECH_CONFIGURATION.value
            elif any(word in message_lower for word in ["slow", "lag", "performance", "speed", "timeout"]):
                return SubIntentClass.TECH_PERFORMANCE.value
            elif any(word in message_lower for word in ["login", "auth", "password", "2fa", "otp"]):
                return SubIntentClass.TECH_AUTHENTICATION.value
            elif any(word in message_lower for word in ["api", "endpoint", "webhook", "sdk"]):
                return SubIntentClass.TECH_API.value

        elif intent == IntentClass.BILLING_ISSUE:
            if any(word in message_lower for word in ["payment fail", "declined", "charge fail"]):
                return SubIntentClass.BILLING_PAYMENT_FAILED.value
            elif any(word in message_lower for word in ["invoice", "bill", "receipt"]):
                return SubIntentClass.BILLING_INVOICE.value
            elif any(word in message_lower for word in ["subscription", "renewal", "plan"]):
                return SubIntentClass.BILLING_SUBSCRIPTION.value
            elif any(word in message_lower for word in ["refund", "credit"]):
                return SubIntentClass.BILLING_REFUND.value
            elif any(word in message_lower for word in ["update", "change", "modify"]):
                return SubIntentClass.BILLING_UPDATE.value
            elif any(word in message_lower for word in ["dispute", "wrong", "incorrect", "mistake"]):
                return SubIntentClass.BILLING_DISPUTE.value

        elif intent == IntentClass.REFUND_REQUEST:
            if any(word in message_lower for word in ["full refund", "complete refund"]):
                return SubIntentClass.REFUND_FULL.value
            elif any(word in message_lower for word in ["partial refund", "pro-rated"]):
                return SubIntentClass.REFUND_PARTIAL.value
            elif any(word in message_lower for word in ["cancel", "cancellation"]):
                return SubIntentClass.REFUND_CANCELLATION.value
            elif any(word in message_lower for word in ["return", "send back"]):
                return SubIntentClass.REFUND_RETURN.value
            elif any(word in message_lower for word in ["dispute", "chargeback"]):
                return SubIntentClass.REFUND_DISPUTE.value

        elif intent == IntentClass.COMPLAINT:
            if any(word in message_lower for word in ["service", "support", "customer service"]):
                return SubIntentClass.COMPLAINT_SERVICE.value
            elif any(word in message_lower for word in ["product", "quality", "broken", "defective"]):
                return SubIntentClass.COMPLAINT_PRODUCT.value
            elif any(word in message_lower for word in ["support", "agent", "representative"]):
                return SubIntentClass.COMPLAINT_SUPPORT.value
            elif any(word in message_lower for word in ["billing", "charge", "invoice"]):
                return SubIntentClass.COMPLAINT_BILLING.value
            elif any(word in message_lower for word in ["delay", "wait", "slow", "late"]):
                return SubIntentClass.COMPLAINT_DELAY.value

        elif intent == IntentClass.GENERAL_INQUIRY:
            if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good evening"]):
                return SubIntentClass.GENERAL_GREETING.value
            elif any(word in message_lower for word in ["question", "ask", "wondering"]):
                return SubIntentClass.GENERAL_QUESTION.value
            elif any(word in message_lower for word in ["feedback", "suggest", "suggestion"]):
                return SubIntentClass.GENERAL_FEEDBACK.value
            elif any(word in message_lower for word in ["information", "info", "tell me", "about"]):
                return SubIntentClass.GENERAL_INFO.value

        return None

    def _log_classification(
        self,
        result: IntentClassificationResult,
        message: str,
        processing_time_ms: float,
    ) -> None:
        """
        Log intent classification for analytics and retraining.

        Args:
            result: The classification result
            message: The original message
            processing_time_ms: Processing time in milliseconds
        """
        log_entry = {
            "classification_id": result.classification_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": self.user_id,
            "is_vip": self.is_vip_user,
            "message": message[:200],  # Truncate for log size
            "intent": result.intent,
            "sub_intent": result.sub_intent,
            "confidence": result.confidence,
            "is_confident": result.is_confident,
            "entities": result.entities,
            "routing_node": result.routing_node,
            "model_variant": result.model_variant,
            "processing_time_ms": processing_time_ms,
            "reasoning": result.reasoning,
        }

        # Log to analytics (structured log for parsing)
        logger.info(f"INTENT_CLASSIFICATION: {log_entry}")

    def _apply_vip_override(self, intent: IntentClass) -> IntentClass:
        """
        Apply intent override for VIP customers.

        VIP customers get priority routing for certain intents.

        Args:
            intent: The original classified intent

        Returns:
            Potentially overridden intent
        """
        if not self.is_vip_user:
            return intent

        # VIP override rules
        # Escalate complaints and refund requests immediately
        if intent in [IntentClass.COMPLAINT, IntentClass.REFUND_REQUEST]:
            logger.info(f"VIP override applied: {intent} -> escalation_priority")
            # Keep the intent but note it's VIP priority
            return intent

        # For technical issues, VIP gets priority routing
        if intent == IntentClass.TECHNICAL_ISSUE:
            logger.info(f"VIP override applied: {intent} -> priority_support")
            return intent

        return intent

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
        Classify the intent of a message with structured JSON output.

        Args:
            message: The message to classify

        Returns:
            IntentClassificationResult with intent, confidence, sub_intent, entities, and routing info
        """
        import time

        start_time = time.time()

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

        # Apply VIP override
        best_intent = self._apply_vip_override(best_intent)

        # Classify sub-intent
        sub_intent = self._classify_sub_intent(message, best_intent)

        # Extract entities
        entities = self._extract_entities(message, best_intent)

        # Get routing node
        routing_node = INTENT_ROUTING_TABLE.get(best_intent, "knowledge_search")

        # Adjust routing for VIP customers
        if self.is_vip_user and best_intent in [IntentClass.COMPLAINT, IntentClass.REFUND_REQUEST]:
            routing_node = "escalation_decision_priority"

        result = IntentClassificationResult(
            intent=best_intent.value,
            confidence=best_confidence,
            sub_intent=sub_intent,
            entities=entities,
            is_confident=best_confidence >= self.confidence_threshold,
            routing_node=routing_node,
            reasoning=reasoning,
            model_variant=self.model_variant,
        )

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Log classification for analytics
        self._log_classification(result, message, processing_time_ms)

        logger.info(
            f"Classified message as {best_intent.value} "
            f"(confidence: {best_confidence:.2f}, sub_intent: {sub_intent}, routing: {routing_node})"
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
