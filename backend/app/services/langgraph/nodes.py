"""LangGraph node specifications for conversation flow."""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.redis import get_queue_redis_client
from app.services.crm.crm_connector import CRMConnector
from app.services.langgraph.angry_customer_handler import AngryCustomerHandler
from app.services.langgraph.context_manager import ContextManager
from app.services.langgraph.customer_profile import CustomerProfileService
from app.services.langgraph.escalation_engine import EscalationEngine, EscalationReason
from app.services.langgraph.handoff import HandoffService
from app.services.langgraph.intent_classifier import IntentClassifier
from app.services.langgraph.language_detector import LanguageDetector
from app.services.langgraph.translation_service import TranslationService
from app.services.langgraph.message_processor import (
    calculate_queue_priority,
    check_duplicate_message,
    detect_message_type,
    extract_message_metadata,
    generate_message_hash,
    sanitize_message,
    validate_message_length,
)
from app.services.langgraph.pending_tickets import PendingTicketsQueue
from app.services.langgraph.priority_detector import PriorityDetector
from app.services.langgraph.sentiment_analyzer import SentimentAnalyzer
from app.services.langgraph.state import ConversationState
from app.services.langgraph.ticket_detector import TicketDetector
from app.services.langgraph.ticket_extractor import TicketExtractor

logger = logging.getLogger(__name__)

# Node timeout configuration (5 seconds per node max)
NODE_TIMEOUT = 5.0


async def receive_query_node(state: ConversationState) -> ConversationState:
    """
    Receive Query Node: Initial node that receives and validates the user query.

    This node:
    - Validates message length (min 1 char, max 2000 chars)
    - Sanitizes message (removes HTML, normalizes Unicode, trims whitespace)
    - Detects message type (text, image, file, voice)
    - Extracts metadata (timestamp, channel, user_id)
    - Checks for duplicate message (prevents double processing)
    - Adds to processing queue with priority based on sentiment
    - Sets initial state
    - Records execution time
    - Creates checkpoint for resumption

    Args:
        state: Current conversation state

    Returns:
        Updated state with validated message
    """
    start_time = time.time()
    state.current_node = "receive_query"
    state.execution_path.append("receive_query")

    try:
        # Step 1: Validate message length
        is_valid, error_message = validate_message_length(state.message)
        if not is_valid:
            raise ValueError(error_message)

        # Step 2: Sanitize message
        original_message = state.message
        sanitized_message = sanitize_message(state.message)
        state.message = sanitized_message

        # Step 3: Detect message type
        message_type = detect_message_type(state.message, state.metadata)
        state.message_type = message_type

        # Step 4: Extract metadata
        extracted_metadata = extract_message_metadata(
            timestamp=state.timestamp,
            channel=state.channel,
            user_id=str(state.user_id) if state.user_id else None,
            conversation_id=str(state.conversation_id) if state.conversation_id else None,
            additional_metadata=state.metadata,
        )
        state.metadata.update(extracted_metadata)

        # Step 5: Check for duplicate message
        redis_client = get_queue_redis_client()
        message_hash = generate_message_hash(
            message=state.message,
            user_id=str(state.user_id) if state.user_id else None,
            conversation_id=str(state.conversation_id) if state.conversation_id else None,
        )
        state.message_hash = message_hash

        is_duplicate = await check_duplicate_message(message_hash, redis_client)
        state.is_duplicate = is_duplicate

        if is_duplicate:
            logger.warning(f"Duplicate message detected and rejected: {message_hash[:16]}...")
            raise ValueError("Duplicate message detected")

        # Step 6: Calculate queue priority based on sentiment (if available)
        # If sentiment is not yet analyzed, use default priority
        if state.sentiment and state.sentiment_score:
            queue_priority = calculate_queue_priority(
                sentiment=state.sentiment,
                sentiment_score=state.sentiment_score,
                message_type=state.message_type,
            )
        else:
            # Default priority based on message type only
            queue_priority = calculate_queue_priority(
                sentiment=None,
                sentiment_score=None,
                message_type=state.message_type,
            )
        state.queue_priority = queue_priority

        # Record intermediate result
        state.intermediate_results["receive_query"] = {
            "validated": True,
            "original_length": len(original_message),
            "sanitized_length": len(sanitized_message),
            "message_type": message_type,
            "message_hash": message_hash[:16] + "...",
            "is_duplicate": is_duplicate,
            "queue_priority": queue_priority,
            "timestamp": state.timestamp.isoformat(),
            "metadata": extracted_metadata,
        }

        # Create checkpoint
        state.checkpoint_id = f"checkpoint_{state.conversation_id}_{int(time.time())}"
        state.can_resume = True

        logger.info(
            f"Received query: {state.message[:50]}... | "
            f"Type: {message_type} | "
            f"Priority: {queue_priority} | "
            f"Hash: {message_hash[:16]}..."
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "receive_query"
        logger.exception(f"Error in receive_query node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["receive_query"] = duration
        logger.debug(f"receive_query node completed in {duration:.2f}s")

    return state


async def language_detection_node(state: ConversationState) -> ConversationState:
    """
    Language Detection Node: Detects the language of the user message and translates to English if needed.

    This node:
    - Detects language from message using fastText/cld3
    - Supports English, Hindi, Spanish, French, Arabic, German
    - Detects language within 100ms performance target
    - Uses 0.85 confidence threshold for acceptance
    - Falls back to English for low confidence or unsupported languages
    - Caches detection result per user (assumes same language for conversation)
    - Translates non-English messages to English for AI processing
    - Preserves original message for database storage

    Args:
        state: Current conversation state

    Returns:
        Updated state with detected language and translation
    """
    start_time = time.time()
    state.current_node = "language_detection"
    state.execution_path.append("language_detection")

    try:
        # Initialize language detector
        detector = LanguageDetector()

        # Get message text
        message = state.current_message if state.current_message else state.message

        if not message:
            logger.warning("No message provided for language detection")
            state.detected_language = "en"
            state.language_name = "English"
            state.language_confidence = 0.0
            state.language_is_supported = True
            state.language_is_fallback = True
            state.language_detection_time_ms = 0.0
            state.language_from_cache = False
            state.original_message = message
            state.translated_message = message
        else:
            # Detect language with caching
            user_id = str(state.user_id) if state.user_id else None
            result = detector.detect_language(
                text=message,
                user_id=user_id,
                use_cache=True,
            )

            # Update state with detection result
            state.detected_language = result.detected_language
            state.language_name = result.language_name
            state.language_confidence = result.confidence
            state.language_is_supported = result.is_supported
            state.language_is_fallback = result.is_fallback
            state.language_detection_time_ms = result.detection_time_ms
            state.language_from_cache = result.from_cache

            # Store original message
            state.original_message = message

            # Translate to English if not already English
            if state.detected_language != "en":
                translator = TranslationService()
                translation_result = translator.translate_to_english(
                    text=message,
                    source_language=state.detected_language,
                )

                if translation_result.success:
                    state.translated_message = translation_result.translated_text
                    state.translation_success = True
                    state.translation_time_ms = translation_result.translation_time_ms
                    logger.info(
                        f"Message translated to English: {state.detected_language} -> en, "
                        f"time: {translation_result.translation_time_ms:.2f}ms"
                    )
                else:
                    # Translation failed, use original message
                    state.translated_message = message
                    state.translation_success = False
                    state.translation_error = translation_result.error
                    state.translation_time_ms = translation_result.translation_time_ms
                    logger.warning(f"Translation failed: {translation_result.error}, using original message")
            else:
                # Already in English, no translation needed
                state.translated_message = message
                state.translation_success = True
                state.translation_time_ms = 0.0

        # Record intermediate result
        state.intermediate_results["language_detection"] = {
            "detected_language": state.detected_language,
            "language_name": state.language_name,
            "confidence": state.language_confidence,
            "is_supported": state.language_is_supported,
            "is_fallback": state.language_is_fallback,
            "detection_time_ms": state.language_detection_time_ms,
            "from_cache": state.language_from_cache,
            "original_message": state.original_message,
            "translated_message": state.translated_message,
            "translation_success": state.translation_success,
            "translation_time_ms": state.translation_time_ms,
        }

        logger.info(
            f"Language detection: {state.language_name} ({state.detected_language}), "
            f"confidence: {state.language_confidence:.2f}, "
            f"supported: {state.language_is_supported}, "
            f"fallback: {state.language_is_fallback}, "
            f"time: {state.language_detection_time_ms:.2f}ms, "
            f"cached: {state.language_from_cache}, "
            f"translated: {state.translated_message != state.original_message}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "language_detection"
        logger.exception(f"Error in language_detection node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["language_detection"] = duration
        logger.debug(f"language_detection node completed in {duration:.2f}s")

    return state


async def intent_detection_node(state: ConversationState) -> ConversationState:
    """
    Intent Detection Node: Detects the user's intent from the message.

    This node:
    - Classifies the user's intent using the IntentClassifier
    - Uses few-shot prompting with training examples
    - Applies confidence threshold (0.70 minimum)
    - Routes to appropriate node based on intent
    - Handles unknown intent for low-confidence results
    - Extracts entities (product names, error codes, amounts, dates)
    - Classifies sub-intent for granular routing
    - Logs classification for analytics and retraining
    - Applies VIP intent override for priority customers
    - Uses A/B testing framework for model variants

    Args:
        state: Current conversation state

    Returns:
        Updated state with detected intent and routing information
    """
    start_time = time.time()
    state.current_node = "intent_detection"
    state.execution_path.append("intent_detection")

    try:
        # Check if user is VIP (from metadata)
        is_vip_user = state.metadata.get("is_vip", False)
        user_id = str(state.user_id) if state.user_id else None

        # Initialize the intent classifier with VIP and A/B testing support
        classifier = IntentClassifier(
            is_vip_user=is_vip_user,
            user_id=user_id,
        )

        # Classify the intent (use translated message if available for AI processing)
        message_to_classify = state.translated_message if state.translated_message else state.message
        classification_result = classifier.classify(message_to_classify)

        # Update state with classification results
        state.detected_intent = classification_result.intent
        state.intent_confidence = classification_result.confidence
        state.intent_sub_intent = classification_result.sub_intent
        state.intent_entities = classification_result.entities
        state.intent_routing_node = classification_result.routing_node
        state.intent_is_confident = classification_result.is_confident
        state.intent_classification_id = classification_result.classification_id
        state.intent_model_variant = classification_result.model_variant

        # Record intermediate result with structured JSON output
        state.intermediate_results["intent_detection"] = {
            "structured_output": classification_result.to_json(),
            "detected_intent": classification_result.intent,
            "confidence": classification_result.confidence,
            "sub_intent": classification_result.sub_intent,
            "entities": classification_result.entities,
            "is_confident": classification_result.is_confident,
            "routing_node": classification_result.routing_node,
            "reasoning": classification_result.reasoning,
            "model_variant": classification_result.model_variant,
            "classification_id": classification_result.classification_id,
            "is_vip_user": is_vip_user,
        }

        logger.info(
            f"Detected intent: {classification_result.intent} "
            f"(confidence: {classification_result.confidence:.2f}, "
            f"sub_intent: {classification_result.sub_intent}, "
            f"routing: {classification_result.routing_node}, "
            f"model: {classification_result.model_variant})"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "intent_detection"
        logger.exception(f"Error in intent_detection node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["intent_detection"] = duration
        logger.debug(f"intent_detection node completed in {duration:.2f}s")

    return state


async def context_management_node(state: ConversationState) -> ConversationState:
    """
    Context Management Node: Retrieves and manages conversation history.

    This node:
    - Fetches last 10 messages from current conversation
    - Formats messages as conversation turns
    - Summarizes older messages beyond last 10 using LLM
    - Injects conversation summary into system prompt
    - Handles conversation branches (unrelated questions)
    - Implements context window management (token limits)

    Args:
        state: Current conversation state

    Returns:
        Updated state with conversation context
    """
    start_time = time.time()
    state.current_node = "context_management"
    state.execution_path.append("context_management")

    try:
        # Initialize context manager
        context_manager = ContextManager()

        # Build conversation context
        conversation_id = str(state.conversation_id) if state.conversation_id else None

        if conversation_id:
            context = await context_manager.build_conversation_context(
                conversation_id=conversation_id,
                current_message=state.message,
            )

            # Update state with context information
            state.conversation_history = [
                {
                    "role": turn.role.value,
                    "content": turn.content,
                    "timestamp": turn.timestamp.isoformat(),
                    "metadata": turn.metadata,
                }
                for turn in context.recent_messages
            ]

            if context.summary:
                state.conversation_summary = context.summary.summary
                state.conversation_topics = context.summary.topics
                state.conversation_entities = context.summary.entities

            state.has_conversation_branch = context.has_conversation_branch
            state.context_window_tokens = context.context_window_tokens
            state.total_message_count = context.total_message_count

            # Format context for prompt injection
            formatted_context = context_manager.format_context_for_prompt(context)

            # Record intermediate result
            state.intermediate_results["context_management"] = {
                "conversation_id": conversation_id,
                "recent_message_count": len(context.recent_messages),
                "has_summary": context.summary is not None,
                "summary": context.summary.summary if context.summary else None,
                "topics": context.summary.topics if context.summary else [],
                "has_branch": context.has_conversation_branch,
                "context_tokens": context.context_window_tokens,
                "total_messages": context.total_message_count,
                "formatted_context": formatted_context,
            }

            logger.info(
                f"Context loaded: {len(context.recent_messages)} recent messages, "
                f"{context.total_message_count - len(context.recent_messages)} summarized, "
                f"{context.context_window_tokens} tokens"
            )
        else:
            # No conversation ID, skip context loading
            logger.warning("No conversation ID provided, skipping context management")
            state.intermediate_results["context_management"] = {
                "skipped": True,
                "reason": "No conversation ID",
            }

    except Exception as e:
        state.error = str(e)
        state.failed_node = "context_management"
        logger.exception(f"Error in context_management node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["context_management"] = duration
        logger.debug(f"context_management node completed in {duration:.2f}s")

    return state


async def customer_profile_node(state: ConversationState) -> ConversationState:
    """
    Customer Profile Node: Fetches customer profile and past tickets for personalization.

    This node:
    - Queries PostgreSQL for customer profile (name, tier, join date)
    - Fetches past tickets (last 5, statuses: resolved, closed)
    - Queries CRM for additional data (purchases, support history)
    - Combines all data into customer context object
    - Identifies VIP customers and flags for priority handling
    - Respects data privacy: only fetches necessary fields

    Args:
        state: Current conversation state

    Returns:
        Updated state with customer context
    """
    start_time = time.time()
    state.current_node = "customer_profile"
    state.execution_path.append("customer_profile")

    try:
        # Initialize customer profile service
        profile_service = CustomerProfileService()

        # Build customer context
        user_id = str(state.user_id) if state.user_id else None
        conversation_id = str(state.conversation_id) if state.conversation_id else None

        if user_id:
            context = await profile_service.build_customer_context(
                user_id=user_id,
                conversation_id=conversation_id,
            )

            # Update state with customer profile information
            if context.profile:
                state.customer_profile = {
                    "customer_id": context.profile.customer_id,
                    "name": context.profile.name,
                    "tier": context.profile.tier.value,
                    "join_date": context.profile.join_date.isoformat(),
                    "language": context.profile.language,
                }
                state.customer_tier = context.profile.tier.value
                state.customer_is_vip = context.profile.is_vip
                state.customer_join_date = context.profile.join_date.isoformat()
                state.customer_language = context.profile.language

            # Update state with past tickets
            state.past_tickets = [
                {
                    "ticket_id": ticket.ticket_id,
                    "category": ticket.category,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "created_at": ticket.created_at.isoformat(),
                    "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                }
                for ticket in context.past_tickets
            ]

            # Update state with CRM data
            if context.crm_data:
                state.crm_data = {
                    "purchases": context.crm_data.purchases,
                    "support_history": context.crm_data.support_history,
                    "last_purchase_date": context.crm_data.last_purchase_date.isoformat() if context.crm_data.last_purchase_date else None,
                    "total_spend": context.crm_data.total_spend,
                    "loyalty_points": context.crm_data.loyalty_points,
                }

            # Update state with priority flag
            state.is_priority_customer = context.is_priority_customer

            # Update metadata with VIP flag for intent classifier
            state.metadata["is_vip"] = context.is_priority_customer

            # Format context for personalization
            formatted_context = profile_service.format_context_for_personalization(context)

            # Record intermediate result
            state.intermediate_results["customer_profile"] = {
                "customer_id": user_id,
                "has_profile": context.profile is not None,
                "tier": context.profile.tier.value if context.profile else None,
                "is_vip": context.profile.is_vip if context.profile else False,
                "past_ticket_count": len(context.past_tickets),
                "has_crm_data": context.crm_data is not None,
                "is_priority_customer": context.is_priority_customer,
                "data_privacy_compliant": context.data_privacy_compliant,
                "formatted_context": formatted_context,
            }

            logger.info(
                f"Customer profile loaded: {context.profile.name if context.profile else 'N/A'} "
                f"({context.profile.tier.value if context.profile else 'N/A'}), "
                f"VIP={context.is_priority_customer}, "
                f"tickets={len(context.past_tickets)}"
            )
        else:
            # No user ID, skip profile loading
            logger.warning("No user ID provided, skipping customer profile")
            state.intermediate_results["customer_profile"] = {
                "skipped": True,
                "reason": "No user ID",
            }

    except Exception as e:
        state.error = str(e)
        state.failed_node = "customer_profile"
        logger.exception(f"Error in customer_profile node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["customer_profile"] = duration
        logger.debug(f"customer_profile node completed in {duration:.2f}s")

    return state


async def sentiment_analysis_node(state: ConversationState) -> ConversationState:
    """
    Sentiment Analysis Node: Detects customer sentiment in real-time.

    This node:
    - Analyzes sentiment using 6 sentiment classes (Positive, Neutral, Negative, Angry, Frustrated, Urgent)
    - Uses keyword-based analysis (placeholder for ML model training)
    - Implements real-time analysis with max 500ms latency
    - Outputs sentiment score (0-1) for each class
    - Tracks sentiment trend across conversation (escalating or de-escalating)
    - Logs sentiment for analytics dashboard

    Args:
        state: Current conversation state

    Returns:
        Updated state with sentiment analysis results
    """
    start_time = time.time()
    state.current_node = "sentiment_analysis"
    state.execution_path.append("sentiment_analysis")

    try:
        # Initialize sentiment analyzer
        analyzer = SentimentAnalyzer()

        # Analyze sentiment with language support
        conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"
        language = state.detected_language if state.detected_language else "en"
        analysis = await analyzer.analyze(state.message, conversation_id, language)

        # Update state with sentiment results
        state.sentiment = analysis.current_result.sentiment_class.value
        state.sentiment_class = analysis.current_result.sentiment_class.value
        state.sentiment_scores = analysis.current_result.scores.model_dump()
        state.sentiment_confidence = analysis.current_result.confidence
        state.sentiment_trend = analysis.trend.value
        state.sentiment_analysis_id = analysis.analysis_id
        state.sentiment_latency_ms = analysis.current_result.latency_ms
        state.sentiment_language = analysis.language
        state.sentiment_model_used = analysis.model_used
        state.sentiment_is_fallback = analysis.is_fallback
        state.sentiment_f1_score = analysis.f1_score

        # Update sentiment history
        state.sentiment_history = [
            {
                "message_id": entry.message_id,
                "sentiment_class": entry.sentiment_class.value,
                "scores": entry.scores.model_dump(),
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in analysis.history
        ]

        # Calculate overall sentiment score (-1 to 1)
        # Positive: positive, neutral
        # Negative: negative, angry, frustrated, urgent
        positive_score = (
            analysis.current_result.scores.positive +
            analysis.current_result.scores.neutral
        )
        negative_score = (
            analysis.current_result.scores.negative +
            analysis.current_result.scores.angry +
            analysis.current_result.scores.frustrated +
            analysis.current_result.scores.urgent
        )
        state.sentiment_score = positive_score - negative_score

        # Record intermediate result
        state.intermediate_results["sentiment_analysis"] = {
            "sentiment_class": analysis.current_result.sentiment_class.value,
            "confidence": analysis.current_result.confidence,
            "scores": analysis.current_result.scores.model_dump(),
            "trend": analysis.trend.value,
            "latency_ms": analysis.current_result.latency_ms,
            "analysis_id": analysis.analysis_id,
            "history_count": len(analysis.history),
            "language": analysis.language,
            "model_used": analysis.model_used,
            "is_fallback": analysis.is_fallback,
            "f1_score": analysis.f1_score,
        }

        logger.info(
            f"Sentiment analysis: {analysis.current_result.sentiment_class.value} "
            f"(confidence: {analysis.current_result.confidence:.2f}, "
            f"trend: {analysis.trend.value}, "
            f"latency: {analysis.current_result.latency_ms:.2f}ms)"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "sentiment_analysis"
        logger.exception(f"Error in sentiment_analysis node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["sentiment_analysis"] = duration
        logger.debug(f"sentiment_analysis node completed in {duration:.2f}s")

    return state


async def angry_customer_handler_node(state: ConversationState) -> ConversationState:
    """
    Angry Customer Handler Node: Detects and handles angry customers.

    This node:
    - Checks if angry sentiment > 0.8 threshold
    - Increases conversation priority to critical
    - Notifies supervisor via Slack/Teams/email
    - Adds visual flag in agent dashboard
    - Reduces AI response time by skipping non-essential nodes
    - Adds sentiment tag to ticket if one is created

    Args:
        state: Current conversation state

    Returns:
        Updated state with angry customer handling actions
    """
    start_time = time.time()
    state.current_node = "angry_customer_handler"
    state.execution_path.append("angry_customer_handler")

    try:
        # Initialize angry customer handler
        handler = AngryCustomerHandler()

        # Check if sentiment analysis is available
        if not state.sentiment_scores:
            logger.info("No sentiment scores available, skipping angry customer check")
            state.intermediate_results["angry_customer_handler"] = {
                "skipped": True,
                "reason": "No sentiment scores",
            }
            return state

        # Handle angry customer
        conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"
        user_id = str(state.user_id) if state.user_id else "unknown"

        handling_result = await handler.handle_angry_customer(
            conversation_id=conversation_id,
            user_id=user_id,
            sentiment_scores=state.sentiment_scores,
            sentiment_class=state.sentiment_class or "neutral",
            message=state.message,
            current_priority=state.queue_priority,
            current_workflow_nodes=state.execution_path,
            notification_channels=["slack", "email"],  # Can be configured
        )

        # Update state with handling results
        state.is_angry_customer = handling_result["is_angry"]
        state.angry_score = handling_result["angry_score"]
        state.angry_customer_actions = handling_result["actions_taken"]

        if handling_result["is_angry"]:
            # Update priority
            state.queue_priority = handling_result["results"].get("priority", state.queue_priority)

            # Store dashboard flag
            state.angry_customer_flag = handling_result["results"].get("dashboard_flag", {})

            # Store notifications
            state.angry_customer_notifications = handling_result["results"].get("notifications", [])

            # Store ticket tag
            state.ticket_sentiment_tag = handling_result["results"].get("ticket_tag")

            # Mark workflow as optimized
            if "optimized_workflow" in handling_result["results"]:
                state.workflow_optimized = True

            logger.warning(
                f"Angry customer handled: {conversation_id}, "
                f"actions: {handling_result['actions_taken']}, "
                f"new priority: {state.queue_priority}"
            )
        else:
            logger.info(f"Customer not angry: {conversation_id}")

        # Record intermediate result
        state.intermediate_results["angry_customer_handler"] = {
            "is_angry": handling_result["is_angry"],
            "angry_score": handling_result["angry_score"],
            "actions_taken": handling_result["actions_taken"],
            "priority": state.queue_priority,
            "workflow_optimized": state.workflow_optimized,
        }

    except Exception as e:
        state.error = str(e)
        state.failed_node = "angry_customer_handler"
        logger.exception(f"Error in angry_customer_handler node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["angry_customer_handler"] = duration
        logger.debug(f"angry_customer_handler node completed in {duration:.2f}s")

    return state


async def ticket_detection_node(state: ConversationState) -> ConversationState:
    """
    Ticket Detection Node: Detects when a ticket should be created automatically.

    This node:
    - Detects trigger conditions (low confidence, explicit request, refund, complaint, repeated issue, angry sentiment)
    - Implements detection logic after each AI response
    - Adds cooldown timer (5 minutes for same issue)
    - Allows user to cancel ticket creation
    - Logs ticket creation decision for audit

    Args:
        state: Current conversation state

    Returns:
        Updated state with ticket detection results
    """
    start_time = time.time()
    state.current_node = "ticket_detection"
    state.execution_path.append("ticket_detection")

    try:
        # Initialize ticket detector
        detector = TicketDetector()

        # Get conversation details
        conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"
        user_id = str(state.user_id) if state.user_id else "unknown"

        # Check for user cancellation
        user_cancelled = detector.check_user_cancellation(state.message)

        # Detect triggers
        triggers = detector.detect_triggers(
            conversation_id=conversation_id,
            user_id=user_id,
            message=state.message,
            ai_confidence=state.sentiment_confidence,
            sentiment_class=state.sentiment_class,
            ai_response_count=len(state.execution_path),
        )

        # Make decision
        decision = detector.make_decision(
            conversation_id=conversation_id,
            user_id=user_id,
            triggers=triggers,
            user_cancelled=user_cancelled,
        )

        # Log decision for audit
        audit_log = detector.log_decision(
            conversation_id=conversation_id,
            user_id=user_id,
            decision=decision,
            triggers=triggers,
            user_cancelled=user_cancelled,
            metadata={
                "message": state.message,
                "sentiment_class": state.sentiment_class,
                "sentiment_confidence": state.sentiment_confidence,
            },
        )

        # Update state with detection results
        state.should_create_ticket = decision.value == "create"
        state.ticket_triggers = [trigger.model_dump() for trigger in triggers]
        state.ticket_decision = decision.value
        state.ticket_cooldown_active = detector._is_cooldown_active(conversation_id)
        state.ticket_user_cancelled = user_cancelled
        state.ticket_audit_log = audit_log.model_dump()

        # Set cooldown if ticket should be created
        if state.should_create_ticket:
            detector._set_cooldown(conversation_id)

        # Record intermediate result
        state.intermediate_results["ticket_detection"] = {
            "decision": decision.value,
            "triggers": [trigger.model_dump() for trigger in triggers],
            "cooldown_active": state.ticket_cooldown_active,
            "user_cancelled": user_cancelled,
            "trigger_count": len(triggers),
        }

        logger.info(
            f"Ticket detection: {decision.value}, "
            f"triggers: {len(triggers)}, "
            f"cooldown: {state.ticket_cooldown_active}, "
            f"cancelled: {user_cancelled}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "ticket_detection"
        logger.exception(f"Error in ticket_detection node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["ticket_detection"] = duration
        logger.debug(f"ticket_detection node completed in {duration:.2f}s")

    return state


async def ticket_extraction_node(state: ConversationState) -> ConversationState:
    """
    Ticket Extraction Node: Extracts structured ticket data from conversation.

    This node:
    - Uses LLM to extract ticket fields from conversation
    - Defines extraction schema (issue_summary, issue_description, priority, category, affected_product, steps_to_reproduce)
    - Validates extracted data completeness
    - Allows human agent to edit before final creation
    - Links ticket to original conversation ID

    Args:
        state: Current conversation state

    Returns:
        Updated state with extracted ticket data
    """
    start_time = time.time()
    state.current_node = "ticket_extraction"
    state.execution_path.append("ticket_extraction")

    try:
        # Only extract if ticket should be created
        if not state.should_create_ticket:
            logger.info("Ticket creation not required, skipping extraction")
            state.intermediate_results["ticket_extraction"] = {
                "skipped": True,
                "reason": "Ticket creation not required",
            }
            return state

        # Initialize ticket extractor
        extractor = TicketExtractor()

        # Get conversation history
        conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"

        # Build conversation history from state
        conversation_history = []
        if state.conversation_history:
            conversation_history = state.conversation_history
        else:
            # Create simple history from current message
            conversation_history = [
                {
                    "role": "user",
                    "content": state.message,
                }
            ]

        # Extract ticket data
        extraction_result = extractor.extract_ticket_data(
            conversation_history=conversation_history,
            conversation_id=conversation_id,
            use_llm=True,
        )

        # Update state with extraction results
        state.extracted_ticket_data = {
            "issue_summary": extraction_result.ticket_data.issue_summary,
            "issue_description": extraction_result.ticket_data.issue_description,
            "priority": extraction_result.ticket_data.priority.value,
            "category": extraction_result.ticket_data.category.value,
            "affected_product": extraction_result.ticket_data.affected_product,
            "steps_to_reproduce": extraction_result.ticket_data.steps_to_reproduce,
            "conversation_id": extraction_result.ticket_data.conversation_id,
        }
        state.ticket_extraction_id = extraction_result.extraction_id
        state.ticket_extraction_confidence = extraction_result.ticket_data.extraction_confidence
        state.ticket_extraction_valid = extraction_result.ticket_data.is_valid
        state.ticket_extraction_errors = extraction_result.ticket_data.validation_errors
        state.ticket_needs_human_review = extraction_result.ticket_data.needs_human_review
        state.ticket_human_edited = extraction_result.human_edited

        # Record intermediate result
        state.intermediate_results["ticket_extraction"] = {
            "extraction_id": extraction_result.extraction_id,
            "valid": extraction_result.ticket_data.is_valid,
            "confidence": extraction_result.ticket_data.extraction_confidence,
            "needs_review": extraction_result.ticket_data.needs_human_review,
            "human_edited": extraction_result.human_edited,
            "validation_errors": extraction_result.ticket_data.validation_errors,
            "ticket_data": state.extracted_ticket_data,
        }

        logger.info(
            f"Ticket extraction completed: {extraction_result.extraction_id}, "
            f"valid={extraction_result.ticket_data.is_valid}, "
            f"confidence={extraction_result.ticket_data.extraction_confidence:.2f}, "
            f"needs_review={extraction_result.ticket_data.needs_human_review}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "ticket_extraction"
        logger.exception(f"Error in ticket_extraction node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["ticket_extraction"] = duration
        logger.debug(f"ticket_extraction node completed in {duration:.2f}s")

    return state


async def pending_tickets_queue_node(state: ConversationState) -> ConversationState:
    """
    Pending Tickets Queue Node: Adds extracted ticket data to pending queue for human review.

    This node:
    - Creates "Pending Tickets" queue in dashboard
    - Displays AI-generated ticket summary with confidence score
    - Allows edit of any field before submission
    - Adds approval button (Create Ticket) and reject button (Not an Issue)
    - Sends approved tickets to ticketing engine
    - Logs rejection reason for AI model improvement

    Args:
        state: Current conversation state

    Returns:
        Updated state with pending ticket queue results
    """
    start_time = time.time()
    state.current_node = "pending_tickets_queue"
    state.execution_path.append("pending_tickets_queue")

    try:
        # Only add to queue if ticket should be created and extraction is valid
        if not state.should_create_ticket or not state.ticket_extraction_valid:
            logger.info("Ticket not required or invalid, skipping pending queue")
            state.intermediate_results["pending_tickets_queue"] = {
                "skipped": True,
                "reason": "Ticket not required or invalid",
            }
            return state

        # Initialize pending tickets queue
        queue = PendingTicketsQueue()

        # Get conversation details
        conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"
        user_id = str(state.user_id) if state.user_id else "unknown"

        # Add ticket to pending queue
        pending_ticket = queue.add_pending_ticket(
            conversation_id=conversation_id,
            user_id=user_id,
            extracted_data=state.extracted_ticket_data,
            extraction_id=state.ticket_extraction_id or "unknown",
            extraction_confidence=state.ticket_extraction_confidence or 0.0,
            metadata={
                "sentiment_class": state.sentiment_class,
                "sentiment_confidence": state.sentiment_confidence,
                "triggers": state.ticket_triggers,
            },
        )

        # Update state with pending ticket results
        state.pending_ticket_id = pending_ticket.ticket_id
        state.pending_ticket_status = pending_ticket.status.value
        state.pending_ticket_created = True

        # Record intermediate result
        state.intermediate_results["pending_tickets_queue"] = {
            "pending_ticket_id": pending_ticket.ticket_id,
            "status": pending_ticket.status.value,
            "extraction_confidence": pending_ticket.extraction_confidence,
            "created_at": pending_ticket.created_at.isoformat(),
            "needs_review": pending_ticket.extraction_confidence < 0.7,
        }

        logger.info(
            f"Pending ticket added to queue: {pending_ticket.ticket_id}, "
            f"status: {pending_ticket.status.value}, "
            f"confidence: {pending_ticket.extraction_confidence:.2f}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "pending_tickets_queue"
        logger.exception(f"Error in pending_tickets_queue node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["pending_tickets_queue"] = duration
        logger.debug(f"pending_tickets_queue node completed in {duration:.2f}s")

    return state


async def priority_detection_node(state: ConversationState) -> ConversationState:
    """
    Priority Detection Node: Determines ticket priority based on various factors.

    This node:
    - Defines priority rules (urgent, high, medium, low)
    - Considers customer tier (VIP gets one level higher)
    - Auto-escalates if no agent responds within SLA
    - Adds priority override rules for specific scenarios

    Args:
        state: Current conversation state

    Returns:
        Updated state with priority detection results
    """
    start_time = time.time()
    state.current_node = "priority_detection"
    state.execution_path.append("priority_detection")

    try:
        # Only detect priority if ticket should be created
        if not state.should_create_ticket:
            logger.info("Ticket not required, skipping priority detection")
            state.intermediate_results["priority_detection"] = {
                "skipped": True,
                "reason": "Ticket not required",
            }
            return state

        # Initialize priority detector
        detector = PriorityDetector()

        # Get conversation details
        ticket_id = state.pending_ticket_id if state.pending_ticket_id else str(state.conversation_id)
        attempts = len(state.execution_path)

        # Detect priority
        detection_result = detector.detect_priority(
            message=state.message,
            sentiment_class=state.sentiment_class,
            angry_score=state.angry_score,
            attempts=attempts,
            customer_tier=state.customer_tier,
            category=state.extracted_ticket_data.get("category"),
            ticket_id=ticket_id,
        )

        # Update state with detection results
        state.detected_priority = detection_result.priority.value
        state.original_priority = detection_result.original_priority.value
        state.priority_reasons = [reason.value for reason in detection_result.reasons]
        state.priority_score = detection_result.score
        state.priority_vip_adjusted = detection_result.vip_adjusted
        state.priority_sla_escalated = detection_result.sla_escalated
        state.priority_override_applied = detection_result.override_applied

        # Update extracted ticket data with detected priority
        state.extracted_ticket_data["priority"] = detection_result.priority.value

        # Track ticket creation for SLA monitoring
        if ticket_id:
            detector.track_ticket_creation(ticket_id)

        # Record intermediate result
        state.intermediate_results["priority_detection"] = {
            "priority": detection_result.priority.value,
            "original_priority": detection_result.original_priority.value,
            "reasons": [reason.value for reason in detection_result.reasons],
            "score": detection_result.score,
            "vip_adjusted": detection_result.vip_adjusted,
            "sla_escalated": detection_result.sla_escalated,
            "override_applied": detection_result.override_applied,
            "override_reason": detection_result.override_reason,
        }

        logger.info(
            f"Priority detection completed: {detection_result.priority.value}, "
            f"original: {detection_result.original_priority.value}, "
            f"vip_adjusted: {detection_result.vip_adjusted}, "
            f"sla_escalated: {detection_result.sla_escalated}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "priority_detection"
        logger.exception(f"Error in priority_detection node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["priority_detection"] = duration
        logger.debug(f"priority_detection node completed in {duration:.2f}s")

    return state


async def crm_lookup_node(state: ConversationState) -> ConversationState:
    """
    CRM Lookup Node: Executes CRM queries in parallel to enrich customer context.

    This node:
    - Executes CRM queries (profile, purchase history, tickets) in parallel for performance
    - Merges CRM data into state.context.customer
    - Handles CRM timeout with fallback to cached data or proceeds without
    - Logs CRM query performance metrics

    Args:
        state: Current conversation state

    Returns:
        Updated state with CRM lookup results
    """
    import asyncio
    from datetime import UTC, datetime

    start_time = time.time()
    state.current_node = "crm_lookup"
    state.execution_path.append("crm_lookup")

    crm_performance_metrics = {
        "profile_fetch_time_ms": 0,
        "purchase_history_fetch_time_ms": 0,
        "tickets_fetch_time_ms": 0,
        "total_fetch_time_ms": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "timeout_occurred": False,
        "queries_executed": 0,
    }

    try:
        # Initialize CRM connector
        connector = CRMConnector(
            crm_type="salesforce",
            base_url="",
            oauth_config=None,
        )

        # Get user details from state
        user_id = str(state.user_id) if state.user_id else "unknown"
        email = state.message_metadata.get("email", "") if state.message_metadata else ""
        phone = state.message_metadata.get("phone", "") if state.message_metadata else ""

        # Define CRM query tasks with timeout handling
        async def fetch_profile_with_timeout():
            try:
                task_start = time.time()
                if email:
                    result = await asyncio.wait_for(
                        connector.fetch_profile_by_email(email),
                        timeout=5.0  # 5 second timeout
                    )
                elif phone:
                    result = await asyncio.wait_for(
                        connector.fetch_profile_by_phone(phone),
                        timeout=5.0
                    )
                else:
                    result = None
                crm_performance_metrics["profile_fetch_time_ms"] = (time.time() - task_start) * 1000
                crm_performance_metrics["queries_executed"] += 1
                return result
            except asyncio.TimeoutError:
                logger.warning("CRM profile fetch timeout, using cached data or proceeding without")
                crm_performance_metrics["timeout_occurred"] = True
                return None
            except Exception as e:
                logger.warning(f"CRM profile fetch error: {e}")
                return None

        async def fetch_purchase_history_with_timeout(customer_id: str):
            try:
                task_start = time.time()
                result = await asyncio.wait_for(
                    connector.fetch_purchase_history(customer_id),
                    timeout=5.0
                )
                crm_performance_metrics["purchase_history_fetch_time_ms"] = (time.time() - task_start) * 1000
                crm_performance_metrics["queries_executed"] += 1
                return result
            except asyncio.TimeoutError:
                logger.warning("CRM purchase history fetch timeout, the system will use cached data or proceed without")
                crm_performance_metrics["timeout_occurred"] = True
                return None
            except Exception as e:
                logger.warning(f"CRM purchase history fetch error: {e}")
                return None

        async def fetch_tickets_with_timeout(customer_id: str, contact_id: str):
            try:
                task_start = time.time()
                internal_tickets = state.past_tickets if state.past_tickets else []
                result = await asyncio.wait_for(
                    connector.fetch_open_tickets(
                        customer_id=customer_id,
                        contact_id=contact_id,
                        internal_tickets=internal_tickets,
                    ),
                    timeout=5.0
                )
                crm_performance_metrics["tickets_fetch_time_ms"] = (time.time() - task_start) * 1000
                crm_performance_metrics["queries_executed"] += 1
                return result
            except asyncio.TimeoutError:
                logger.warning("CRM tickets fetch timeout, the system will use cached data or proceed without")
                crm_performance_metrics["timeout_occurred"] = True
                return None
            except Exception as e:
                logger.warning(f"CRM tickets fetch error: {e}")
                return None

        # Execute CRM queries in parallel
        crm_profile = await fetch_profile_with_timeout()

        # If profile fetched, execute remaining queries in parallel
        if crm_profile and crm_profile.customer_id:
            purchase_history_task = fetch_purchase_history_with_timeout(crm_profile.customer_id)
            tickets_task = fetch_tickets_with_timeout(
                crm_profile.customer_id,
                crm_profile.contact_id or ""
            )

            # Execute in parallel
            purchase_history, crm_tickets_summary = await asyncio.gather(
                purchase_history_task,
                tickets_task,
                return_exceptions=True
            )

            # Handle exceptions from gather
            if isinstance(purchase_history, Exception):
                logger.warning(f"Purchase history fetch failed: {purchase_history}")
                purchase_history = None
            if isinstance(crm_tickets_summary, Exception):
                logger.warning(f"Tickets fetch failed: {crm_tickets_summary}")
                crm_tickets_summary = None
        else:
            purchase_history = None
            crm_tickets_summary = None

        # Merge CRM data into state.context.customer
        if crm_profile:
            state.crm_contact_id = crm_profile.contact_id
            state.crm_account_id = crm_profile.account_id
            state.crm_data_synced = True

            # Merge into customer profile context
            state.customer_profile.update({
                "customer_name": crm_profile.customer_name,
                "customer_tier": crm_profile.customer_tier,
                "subscription_plan": crm_profile.subscription_plan,
                "account_age_days": crm_profile.account_age_days,
                "crm_contact_id": crm_profile.contact_id,
                "crm_account_id": crm_profile.account_id,
            })

            # Update customer tier
            if crm_profile.customer_tier:
                state.customer_tier = crm_profile.customer_tier
                if crm_profile.customer_tier == "vip":
                    state.customer_is_vip = True

        # Merge purchase history
        if purchase_history:
            state.purchase_history_summary = purchase_history.model_dump()
            state.total_transactions = purchase_history.total_transactions
            state.total_customer_value = purchase_history.customer_value
            state.failed_payment_count = purchase_history.failed_payment_count
            state.subscription_count = purchase_history.subscription_count
            state.one_time_count = purchase_history.one_time_count

            state.crm_data.update({
                "total_transactions": purchase_history.total_transactions,
                "total_customer_value": purchase_history.customer_value,
                "failed_payment_count": purchase_history.failed_payment_count,
                "subscription_count": purchase_history.subscription_count,
                "one_time_count": purchase_history.one_time_count,
            })

            if purchase_history.customer_value > 1000:
                state.is_priority_customer = True

        # Merge CRM tickets
        if crm_tickets_summary:
            state.crm_open_tickets = [t.model_dump() for t in crm_tickets_summary.tickets]
            state.crm_total_tickets = crm_tickets_summary.total_tickets
            state.crm_open_tickets_count = crm_tickets_summary.open_tickets
            state.crm_high_priority_tickets = crm_tickets_summary.high_priority_tickets

            if crm_tickets_summary.open_tickets > 0:
                state.crm_existing_ticket_message = connector.generate_existing_ticket_message(
                    crm_tickets_summary.tickets
                )

            if state.should_create_ticket and state.extracted_ticket_data:
                subject = state.extracted_ticket_data.get("issue_summary", "")
                description = state.extracted_ticket_data.get("issue_description", "")
                duplicate_ticket = connector.check_duplicate_ticket(
                    subject, description, crm_tickets_summary.tickets
                )
                if duplicate_ticket:
                    state.crm_duplicate_ticket_detected = True
                    state.should_create_ticket = False
                    logger.info(f"Duplicate CRM ticket detected: {duplicate_ticket.ticket_id}")

            state.crm_data.update({
                "crm_total_tickets": crm_tickets_summary.total_tickets,
                "crm_open_tickets_count": crm_tickets_summary.open_tickets,
                "crm_high_priority_tickets": crm_tickets_summary.high_priority_tickets,
            })

        # Get quota information
        quota_info = connector.get_quota_info()
        if quota_info:
            state.crm_quota_remaining = quota_info["quota_remaining"]
            state.crm_rate_limited = quota_info["status"] == "limited"

        # Record sync timestamp
        state.crm_sync_timestamp = datetime.now(UTC).isoformat()

        # Calculate total fetch time
        crm_performance_metrics["total_fetch_time_ms"] = (time.time() - start_time) * 1000

        # Record intermediate result with performance metrics
        state.intermediate_results["crm_lookup"] = {
            "crm_type": connector.crm_type,
            "profile_fetched": crm_profile is not None,
            "purchase_history_fetched": purchase_history is not None,
            "tickets_fetched": crm_tickets_summary is not None,
            "data_synced": state.crm_data_synced,
            "sync_timestamp": state.crm_sync_timestamp,
            "performance_metrics": crm_performance_metrics,
        }

        # Log performance metrics
        logger.info(
            f"CRM lookup completed - Total: {crm_performance_metrics['total_fetch_time_ms']:.2f}ms, "
            f"Profile: {crm_performance_metrics['profile_fetch_time_ms']:.2f}ms, "
            f"Purchase History: {crm_performance_metrics['purchase_history_fetch_time_ms']:.2f}ms, "
            f"Tickets: {crm_performance_metrics['tickets_fetch_time_ms']:.2f}ms, "
            f"Queries: {crm_performance_metrics['queries_executed']}, "
            f"Timeout: {crm_performance_metrics['timeout_occurred']}"
        )

        # Close connector
        await connector.close()

    except Exception as e:
        state.error = str(e)
        state.failed_node = "crm_lookup"
        logger.exception(f"Error in crm_lookup node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["crm_lookup"] = duration
        logger.debug(f"crm_lookup node completed in {duration:.2f}s")

    return state


async def escalation_node(state: ConversationState) -> ConversationState:
    """
    Escalation Node: Evaluates AI confidence and makes escalation decisions.

    This node:
    - Evaluates AI confidence score against thresholds
    - Implements immediate escalation for confidence < 0.60
    - Implements rephrase and escalate for 0.60 ≤ confidence < 0.70
    - Tracks confidence per message, escalates on 2 consecutive low-confidence
    - Tracks failed attempts (same/similar messages after AI response)
    - Escalates after 3 failed attempts
    - VIP customers get preferential escalation (lower thresholds, negative sentiment escalation)
    - Logs low-confidence queries for model improvement

    Args:
        state: Current conversation state

    Returns:
        Updated state with escalation decision
    """
    start_time = time.time()
    state.current_node = "escalation"
    state.execution_path.append("escalation")

    try:
        # Get customer type from profile
        customer_type = state.customer_tier if state.customer_tier else state.customer_profile.get("customer_type", "regular")
        if state.customer_is_vip:
            customer_type = "vip"

        # Initialize escalation engine with customer type
        escalation_engine = EscalationEngine(customer_type=customer_type)

        # Get confidence score from state (would be set by AI response generation)
        # For now, use a placeholder or extract from response metadata
        confidence = state.response_metadata.get("confidence", 0.85) if state.response_metadata else 0.85

        # Update state with current confidence
        state.ai_confidence = confidence
        state.confidence_history.append(confidence)

        # Check for negative sentiment escalation for VIP customers
        sentiment_decision = escalation_engine.evaluate_negative_sentiment(state.sentiment)
        if sentiment_decision and sentiment_decision.should_escalate:
            state.should_escalate = True
            state.escalation_reason = sentiment_decision.reason.value if sentiment_decision.reason else None
            state.escalation_payload = sentiment_decision.escalation_payload
            logger.warning(f"VIP escalation triggered by negative sentiment: {state.escalation_reason}")
        else:
            # Track failed attempts (same/similar message after AI response)
            current_message = state.current_message if state.current_message else ""
            is_failed_attempt, failed_attempt_reason = escalation_engine.is_failed_attempt(
                current_message=current_message,
                previous_messages=state.previous_messages,
                last_ai_response=state.last_ai_response,
            )

            if is_failed_attempt:
                state.failed_attempt_count += 1
                state.attempt_reasons.append(failed_attempt_reason)
                logger.warning(f"Failed attempt detected: {failed_attempt_reason}, count: {state.failed_attempt_count}")
            else:
                # Reset counter if not a failed attempt (successful resolution)
                if state.failed_attempt_count > 0:
                    state.failed_attempt_count = escalation_engine.reset_failed_attempt_count()
                    state.attempt_reasons = []
                    logger.info("Failed attempt count reset after successful resolution")

            # Add current message to previous messages
            state.previous_messages.append(current_message)

            # Evaluate failed attempts and make escalation decision
            failed_attempt_decision = escalation_engine.evaluate_failed_attempts(
                failed_attempt_count=state.failed_attempt_count,
                attempt_reasons=state.attempt_reasons,
            )

            # If failed attempts trigger escalation, use that decision
            if failed_attempt_decision.should_escalate:
                state.should_escalate = True
                state.escalation_reason = failed_attempt_decision.reason.value if failed_attempt_decision.reason else None
                state.escalation_payload = failed_attempt_decision.escalation_payload
                logger.warning(f"Escalation triggered by failed attempts: {state.escalation_reason}")
            else:
                # Otherwise, evaluate confidence-based escalation
                decision = escalation_engine.evaluate_confidence(
                    confidence=confidence,
                    low_confidence_count=state.low_confidence_count,
                    rephrase_attempted=state.rephrase_attempted,
                    rephrase_confidence=state.rephrase_confidence,
                )

                # Update state with decision
                state.should_escalate = decision.should_escalate
                state.escalation_reason = decision.reason.value if decision.reason else None
                state.low_confidence_count = decision.low_confidence_count

                # Check if rephrase should be attempted
                if not decision.should_escalate and escalation_engine.should_rephrase(confidence):
                    state.rephrase_attempted = True
                    logger.info(f"Rephrase recommended for confidence {confidence:.2f}")
                else:
                    state.rephrase_attempted = False

        # Log low-confidence queries for model improvement
        if confidence < escalation_engine.min_confidence_threshold:
            query_id = str(uuid.uuid4())
            conversation_id = str(state.conversation_id) if state.conversation_id else "unknown"
            user_id = str(state.user_id) if state.user_id else "unknown"
            query = state.current_message if state.current_message else ""

            escalation_engine.log_low_confidence_query(
                query_id=query_id,
                conversation_id=conversation_id,
                user_id=user_id,
                query=query,
                confidence_score=confidence,
                rephrase_attempted=state.rephrase_attempted,
                rephrase_confidence=state.rephrase_confidence,
                escalated=state.should_escalate,
                escalation_reason=state.escalation_reason,
                context={
                    "intent": state.intent,
                    "sentiment": state.sentiment,
                    "customer_tier": state.customer_tier,
                    "failed_attempt_count": state.failed_attempt_count,
                },
            )

        # Record intermediate result
        state.intermediate_results["escalation"] = {
            "confidence": confidence,
            "should_escalate": state.should_escalate,
            "reason": state.escalation_reason,
            "low_confidence_count": state.low_confidence_count,
            "rephrase_attempted": state.rephrase_attempted,
            "confidence_history": state.confidence_history,
            "failed_attempt_count": state.failed_attempt_count,
            "attempt_reasons": state.attempt_reasons,
            "escalation_payload": state.escalation_payload,
            "customer_type": customer_type,
            "is_vip": escalation_engine.is_vip,
        }

        logger.info(
            f"Escalation evaluation - Confidence: {confidence:.2f}, "
            f"Should Escalate: {state.should_escalate}, "
            f"Reason: {state.escalation_reason}, "
            f"Low Confidence Count: {state.low_confidence_count}, "
            f"Failed Attempt Count: {state.failed_attempt_count}, "
            f"Customer Type: {customer_type}, "
            f"Is VIP: {escalation_engine.is_vip}"
        )

        # Prepare handoff data if escalation is triggered
        if state.should_escalate:
            handoff_service = HandoffService()
            
            # Prepare handoff data
            handoff_data = handoff_service.prepare_handoff(
                conversation_id=str(state.conversation_id) if state.conversation_id else "unknown",
                escalation_reason=state.escalation_reason,
                state=state.model_dump(),
            )
            
            # Update state with handoff data
            state.handoff_data = handoff_data.model_dump()
            state.handoff_prepared = True
            
            # Get transfer message for customer
            state.transfer_message = handoff_service.get_transfer_message(is_vip=escalation_engine.is_vip)
            
            logger.info(f"Handoff data prepared for conversation {state.conversation_id}")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "escalation"
        logger.exception(f"Error in escalation node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["escalation"] = duration
        logger.debug(f"escalation node completed in {duration:.2f}s")

    return state


async def escalation_decision_node(state: ConversationState) -> ConversationState:
    """
    Escalation Decision Node: Centralized escalation logic as last step before Response Delivery.

    This node evaluates all escalation conditions and makes the final escalation decision:
    - Sentiment == "angry" and score > 0.8
    - Confidence < 0.70
    - Failed attempts > 3
    - Customer type in ("vip", "enterprise") and sentiment != "positive"
    - User-triggered escalation (explicit request)

    If escalated, skips Response Generation and goes to Human Handoff.

    Args:
        state: Current conversation state

    Returns:
        Updated state with escalation decision
    """
    start_time = time.time()
    state.current_node = "escalation_decision"
    state.execution_path.append("escalation_decision")

    try:
        logger.info("Evaluating escalation decision")

        # Initialize escalation decision
        should_escalate = False
        escalation_reason = None
        escalation_priority = "medium"
        decision_details = []

        # Condition 1: Sentiment == "angry" and score > 0.8
        sentiment = state.sentiment
        sentiment_score = state.sentiment_score if hasattr(state, 'sentiment_score') else 0.0
        if sentiment == "angry" and sentiment_score > 0.8:
            should_escalate = True
            escalation_reason = "angry_customer"
            escalation_priority = "urgent"
            decision_details.append(f"Angry customer detected: sentiment={sentiment}, score={sentiment_score:.2f}")
            logger.warning(f"Escalation triggered: Angry customer with score {sentiment_score:.2f}")

        # Condition 2: Confidence < 0.70
        confidence = state.ai_confidence if state.ai_confidence is not None else 0.85
        if confidence < 0.70:
            should_escalate = True
            escalation_reason = "low_confidence"
            escalation_priority = "high" if confidence < 0.60 else "medium"
            decision_details.append(f"Low confidence: {confidence:.2f} < 0.70")
            logger.warning(f"Escalation triggered: Low confidence {confidence:.2f}")

        # Condition 3: Failed attempts > 3
        failed_attempts = state.failed_attempt_count
        if failed_attempts > 3:
            should_escalate = True
            escalation_reason = "failed_attempts"
            escalation_priority = "high"
            decision_details.append(f"Failed attempts: {failed_attempts} > 3")
            logger.warning(f"Escalation triggered: Failed attempts {failed_attempts}")

        # Condition 4: Customer type in ("vip", "enterprise") and sentiment != "positive"
        customer_type = state.customer_tier if state.customer_tier else state.customer_profile.get("customer_type", "regular")
        is_vip_or_enterprise = customer_type.lower() in ["vip", "enterprise"]
        if is_vip_or_enterprise and sentiment != "positive":
            should_escalate = True
            escalation_reason = "vip_customer_sentiment"
            escalation_priority = "high"
            decision_details.append(f"VIP/Enterprise customer with non-positive sentiment: type={customer_type}, sentiment={sentiment}")
            logger.warning(f"Escalation triggered: VIP/Enterprise customer with sentiment {sentiment}")

        # Condition 5: User-triggered escalation (explicit request)
        user_triggered = state.user_triggered_escalation
        if user_triggered:
            should_escalate = True
            escalation_reason = "user_requested"
            escalation_priority = "urgent"
            decision_details.append("User explicitly requested escalation")
            logger.warning("Escalation triggered: User requested escalation")

        # Update state with escalation decision
        state.should_escalate = should_escalate
        state.escalation_reason = escalation_reason
        state.escalation_priority = escalation_priority

        # Build escalation payload
        state.escalation_payload = {
            "decision_timestamp": datetime.now(UTC).isoformat(),
            "conditions_evaluated": decision_details,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "confidence": confidence,
            "failed_attempts": failed_attempts,
            "customer_type": customer_type,
            "is_vip_or_enterprise": is_vip_or_enterprise,
            "user_triggered": user_triggered,
        }

        # Log escalation decision for analytics
        logger.info(
            f"Escalation Decision - Should Escalate: {should_escalate}, "
            f"Reason: {escalation_reason}, "
            f"Priority: {escalation_priority}, "
            f"Details: {decision_details}"
        )

        # Record intermediate result
        state.intermediate_results["escalation_decision"] = {
            "should_escalate": should_escalate,
            "reason": escalation_reason,
            "priority": escalation_priority,
            "details": decision_details,
            "evaluated_conditions": {
                "angry_customer": sentiment == "angry" and sentiment_score > 0.8,
                "low_confidence": confidence < 0.70,
                "failed_attempts": failed_attempts > 3,
                "vip_sentiment": is_vip_or_enterprise and sentiment != "positive",
                "user_triggered": user_triggered,
            },
        }

        # If escalated, prepare handoff data
        if should_escalate:
            handoff_service = HandoffService()
            
            # Prepare handoff data
            handoff_data = handoff_service.prepare_handoff(
                conversation_id=str(state.conversation_id) if state.conversation_id else "unknown",
                escalation_reason=escalation_reason,
                state=state.model_dump(),
            )
            
            # Update state with handoff data
            state.handoff_data = handoff_data.model_dump()
            state.handoff_prepared = True
            
            # Get transfer message for customer
            state.transfer_message = handoff_service.get_transfer_message(is_vip=is_vip_or_enterprise)
            
            logger.info(f"Handoff data prepared for escalation decision node")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "escalation_decision"
        logger.exception(f"Error in escalation decision node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["escalation_decision"] = duration
        logger.debug(f"escalation_decision node completed in {duration:.2f}s")

    return state


async def crm_integration_node(state: ConversationState) -> ConversationState:
    """
    CRM Integration Node: Integrates with CRM system to sync customer data and fetch profiles.

    This node:
    - Integrates with CRM (Salesforce/HubSpot/Zoho/Freshworks)
    - Uses OAuth 2.0 authentication
    - Implements rate-limited API client with retry logic
    - Syncs Contact, Account, Purchase, Support Ticket data
    - Fetches customer profile by email or phone
    - Caches CRM data in Redis (1 hour TTL)
    - Handles missing customer (creates minimal profile)
    - Respects CRM field-level security
    - Handles API quota management

    Args:
        state: Current conversation state

    Returns:
        Updated state with CRM integration results
    """
    start_time = time.time()
    state.current_node = "crm_integration"
    state.execution_path.append("crm_integration")

    try:
        # Initialize CRM connector (placeholder - requires configuration)
        # In production, this would use environment variables or config
        connector = CRMConnector(
            crm_type="salesforce",  # Configurable based on requirements
            base_url="",  # From config
            oauth_config=None,  # From config
        )

        # Get user details from state
        user_id = str(state.user_id) if state.user_id else "unknown"
        email = state.message_metadata.get("email", "") if state.message_metadata else ""
        phone = state.message_metadata.get("phone", "") if state.message_metadata else ""

        # Fetch customer profile from CRM
        crm_profile = None
        if email:
            crm_profile = await connector.fetch_profile_by_email(email)
        elif phone:
            crm_profile = await connector.fetch_profile_by_phone(phone)

        # Update state with CRM profile data
        if crm_profile:
            state.crm_contact_id = crm_profile.contact_id
            state.crm_account_id = crm_profile.account_id
            state.crm_data_synced = True

            # Update customer profile context with CRM data
            state.customer_profile.update({
                "customer_name": crm_profile.customer_name,
                "customer_tier": crm_profile.customer_tier,
                "subscription_plan": crm_profile.subscription_plan,
                "account_age_days": crm_profile.account_age_days,
                "crm_contact_id": crm_profile.contact_id,
                "crm_account_id": crm_profile.account_id,
            })

            # Update customer tier if available from CRM
            if crm_profile.customer_tier:
                state.customer_tier = crm_profile.customer_tier
                if crm_profile.customer_tier == "vip":
                    state.customer_is_vip = True

            # Fetch purchase history if customer ID available
            purchase_history = None
            if crm_profile.customer_id:
                purchase_history = await connector.fetch_purchase_history(crm_profile.customer_id)

            # Update state with purchase history data
            if purchase_history:
                state.purchase_history_summary = purchase_history.model_dump()
                state.total_transactions = purchase_history.total_transactions
                state.total_customer_value = purchase_history.customer_value
                state.failed_payment_count = purchase_history.failed_payment_count
                state.subscription_count = purchase_history.subscription_count
                state.one_time_count = purchase_history.one_time_count

                # Update CRM data with purchase history
                state.crm_data.update({
                    "total_transactions": purchase_history.total_transactions,
                    "total_customer_value": purchase_history.customer_value,
                    "failed_payment_count": purchase_history.failed_payment_count,
                    "subscription_count": purchase_history.subscription_count,
                    "one_time_count": purchase_history.one_time_count,
                })

                # Update priority customer based on customer value
                if purchase_history.customer_value > 1000:  # Threshold for high-value customer
                    state.is_priority_customer = True

            # Fetch open tickets from CRM if contact ID available
            crm_tickets_summary = None
            if crm_profile and crm_profile.contact_id:
                # Get internal tickets for cross-referencing
                internal_tickets = state.past_tickets if state.past_tickets else []
                crm_tickets_summary = await connector.fetch_open_tickets(
                    customer_id=crm_profile.customer_id,
                    contact_id=crm_profile.contact_id,
                    internal_tickets=internal_tickets,
                )

            # Update state with CRM tickets data
            if crm_tickets_summary:
                state.crm_open_tickets = [t.model_dump() for t in crm_tickets_summary.tickets]
                state.crm_total_tickets = crm_tickets_summary.total_tickets
                state.crm_open_tickets_count = crm_tickets_summary.open_tickets
                state.crm_high_priority_tickets = crm_tickets_summary.high_priority_tickets

                # Generate message for customer about existing tickets
                if crm_tickets_summary.open_tickets > 0:
                    state.crm_existing_ticket_message = connector.generate_existing_ticket_message(
                        crm_tickets_summary.tickets
                    )

                # Check for duplicate ticket if ticket creation is being considered
                if state.should_create_ticket and state.extracted_ticket_data:
                    subject = state.extracted_ticket_data.get("issue_summary", "")
                    description = state.extracted_ticket_data.get("issue_description", "")
                    duplicate_ticket = connector.check_duplicate_ticket(
                        subject, description, crm_tickets_summary.tickets
                    )
                    if duplicate_ticket:
                        state.crm_duplicate_ticket_detected = True
                        # Skip ticket creation if duplicate exists
                        state.should_create_ticket = False
                        logger.info(f"Duplicate CRM ticket detected: {duplicate_ticket.ticket_id}")

                # Update CRM data with ticket information
                state.crm_data.update({
                    "crm_total_tickets": crm_tickets_summary.total_tickets,
                    "crm_open_tickets_count": crm_tickets_summary.open_tickets,
                    "crm_high_priority_tickets": crm_tickets_summary.high_priority_tickets,
                })

        # Sync contact if CRM client is configured
        if connector.client and email:
            # Extract name from metadata or use placeholder
            first_name = state.message_metadata.get("first_name", "User") if state.message_metadata else "User"
            last_name = state.message_metadata.get("last_name", "") if state.message_metadata else ""

            contact = await connector.sync_contact(
                user_id=user_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )

            if contact:
                state.crm_contact_id = contact.contact_id
                state.crm_data_synced = True

        # Get quota information
        quota_info = connector.get_quota_info()
        if quota_info:
            state.crm_quota_remaining = quota_info["quota_remaining"]
            state.crm_rate_limited = quota_info["status"] == "limited"

        # Record sync timestamp
        from datetime import UTC, datetime
        state.crm_sync_timestamp = datetime.now(UTC).isoformat()

        # Record intermediate result
        state.intermediate_results["crm_integration"] = {
            "crm_type": connector.crm_type,
            "profile_fetched": crm_profile is not None,
            "contact_synced": state.crm_contact_id is not None,
            "contact_id": state.crm_contact_id,
            "account_id": state.crm_account_id,
            "data_synced": state.crm_data_synced,
            "sync_timestamp": state.crm_sync_timestamp,
            "quota_remaining": state.crm_quota_remaining,
            "rate_limited": state.crm_rate_limited,
            "customer_tier": state.customer_tier,
            "customer_is_vip": state.customer_is_vip,
            "purchase_history_fetched": purchase_history is not None,
            "total_transactions": state.total_transactions,
            "total_customer_value": state.total_customer_value,
            "failed_payment_count": state.failed_payment_count,
            "subscription_count": state.subscription_count,
            "one_time_count": state.one_time_count,
            "crm_tickets_fetched": crm_tickets_summary is not None,
            "crm_total_tickets": state.crm_total_tickets,
            "crm_open_tickets_count": state.crm_open_tickets_count,
            "crm_high_priority_tickets": state.crm_high_priority_tickets,
            "crm_duplicate_ticket_detected": state.crm_duplicate_ticket_detected,
            "crm_existing_ticket_message": state.crm_existing_ticket_message is not None,
        }

        logger.info(
            f"CRM integration completed: {connector.crm_type}, "
            f"profile_fetched: {crm_profile is not None}, "
            f"contact_synced: {state.crm_contact_id is not None}, "
            f"quota_remaining: {state.crm_quota_remaining}"
        )

        # Close connector
        await connector.close()

    except Exception as e:
        state.error = str(e)
        state.failed_node = "crm_integration"
        logger.exception(f"Error in crm_integration node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["crm_integration"] = duration
        logger.debug(f"crm_integration node completed in {duration:.2f}s")

    return state


async def knowledge_search_node(state: ConversationState) -> ConversationState:
    """
    Knowledge Search Node: Searches the knowledge base for relevant information.

    This node:
    - Constructs search query from message and intent
    - Searches knowledge base
    - Returns relevant documents/answers

    Args:
        state: Current conversation state

    Returns:
        Updated state with search results
    """
    start_time = time.time()
    state.current_node = "knowledge_search"
    state.execution_path.append("knowledge_search")

    try:
        # Construct search query (use translated message if available for AI processing)
        search_query = state.translated_message if state.translated_message else state.message
        if state.detected_intent:
            search_query = f"{state.detected_intent}: {search_query}"

        state.search_query = search_query

        # Simulate knowledge base search (in production, use vector search)
        # For now, return empty results
        search_results = []

        # In a real implementation, you would:
        # 1. Use a vector database (e.g., Pinecone, Weaviate)
        # 2. Perform semantic search
        # 3. Return top-k results with relevance scores

        state.search_results = search_results

        # Record intermediate result
        state.intermediate_results["knowledge_search"] = {
            "search_query": search_query,
            "result_count": len(search_results),
        }

        logger.info(f"Knowledge search completed: {len(search_results)} results")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "knowledge_search"
        logger.exception(f"Error in knowledge_search node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["knowledge_search"] = duration
        logger.debug(f"knowledge_search node completed in {duration:.2f}s")

    return state


async def response_generation_node(state: ConversationState) -> ConversationState:
    """
    Response Generation Node: Generates a response based on search results and context.

    This node:
    - Uses LLM to generate response
    - Incorporates search results if available
    - Returns generated response

    Args:
        state: Current conversation state

    Returns:
        Updated state with generated response
    """
    start_time = time.time()
    state.current_node = "response_generation"
    state.execution_path.append("response_generation")

    try:
        # Generate response (in production, use actual LLM)
        # For now, use simple rule-based responses
        intent = state.detected_intent or "general"

        responses = {
            "greeting": "Hello! How can I help you today?",
            "support_request": "I'd be happy to help you with that. Could you please provide more details?",
            "complaint": "I'm sorry to hear you're having issues. Let me help you resolve this.",
            "question": "That's a great question. Let me look into that for you.",
            "farewell": "You're welcome! Feel free to reach out if you need anything else.",
            "general": "I understand. How can I assist you further?",
        }

        generated_response = responses.get(intent, responses["general"])

        # If we have search results, incorporate them
        if state.search_results:
            generated_response += " I found some relevant information that might help."

        # Note: The response is generated in English, will be translated back in return_response_node
        state.generated_response = generated_response
        state.response_source = "ai" if not state.search_results else "knowledge"

        # Record intermediate result
        state.intermediate_results["response_generation"] = {
            "generated_response": generated_response,
            "source": state.response_source,
            "generated_in_english": True,
        }

        logger.info(f"Generated response in English: {generated_response[:50]}...")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "response_generation"
        logger.exception(f"Error in response_generation node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["response_generation"] = duration
        logger.debug(f"response_generation node completed in {duration:.2f}s")

    return state


async def sentiment_analysis_node(state: ConversationState) -> ConversationState:
    """
    Sentiment Analysis Node: Analyzes the sentiment of the user message.

    This node:
    - Determines sentiment (positive, negative, neutral)
    - Returns sentiment score (-1 to 1)
    - Used for escalation decisions

    Args:
        state: Current conversation state

    Returns:
        Updated state with sentiment analysis
    """
    start_time = time.time()
    state.current_node = "sentiment_analysis"
    state.execution_path.append("sentiment_analysis")

    try:
        # Use translated message for sentiment analysis (English for AI processing)
        message = (state.translated_message if state.translated_message else state.message).lower()

        # Simple sentiment analysis (in production, use a proper sentiment analyzer)
        positive_words = ["good", "great", "excellent", "happy", "love", "thanks", "thank"]
        negative_words = ["bad", "terrible", "awful", "hate", "angry", "frustrated", "issue"]

        positive_count = sum(1 for word in positive_words if word in message)
        negative_count = sum(1 for word in negative_words if word in message)

        if positive_count > negative_count:
            sentiment = "positive"
            score = 0.5
        elif negative_count > positive_count:
            sentiment = "negative"
            score = -0.5
        else:
            sentiment = "neutral"
            score = 0.0

        state.sentiment = sentiment
        state.sentiment_score = score

        # Record intermediate result
        state.intermediate_results["sentiment_analysis"] = {
            "sentiment": sentiment,
            "score": score,
            "analyzed_message": state.translated_message if state.translated_message else state.message,
        }

        logger.info(f"Sentiment analysis: {sentiment} (score: {score})")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "sentiment_analysis"
        logger.exception(f"Error in sentiment_analysis node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["sentiment_analysis"] = duration
        logger.debug(f"sentiment_analysis node completed in {duration:.2f}s")

    return state


async def escalation_decision_node(state: ConversationState) -> ConversationState:
    """
    Escalation Decision Node: Decides whether to escalate to human agent.

    This node:
    - Evaluates sentiment, intent, and complexity
    - Determines if human intervention is needed
    - Returns escalation decision

    Args:
        state: Current conversation state

    Returns:
        Updated state with escalation decision
    """
    start_time = time.time()
    state.current_node = "escalation_decision"
    state.execution_path.append("escalation_decision")

    try:
        should_escalate = False
        escalation_reason = None

        # Escalation criteria
        if state.sentiment == "negative" and state.sentiment_score < -0.3:
            should_escalate = True
            escalation_reason = "Negative sentiment detected"

        elif state.detected_intent == "complaint":
            should_escalate = True
            escalation_reason = "Complaint detected"

        elif state.intent_confidence and state.intent_confidence < 0.5:
            should_escalate = True
            escalation_reason = "Low intent confidence"

        state.should_escalate = should_escalate
        state.escalation_reason = escalation_reason

        # Record intermediate result
        state.intermediate_results["escalation_decision"] = {
            "should_escalate": should_escalate,
            "reason": escalation_reason,
        }

        logger.info(f"Escalation decision: {should_escalate} (reason: {escalation_reason})")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "escalation_decision"
        logger.exception(f"Error in escalation_decision node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["escalation_decision"] = duration
        logger.debug(f"escalation_decision node completed in {duration:.2f}s")

    return state


async def return_response_node(state: ConversationState) -> ConversationState:
    """
    Return Response Node: Finalizes and returns the response with translation if needed.

    This node:
    - Selects appropriate response
    - Adds escalation message if needed
    - Translates response back to customer's language if not English
    - Handles translation failures with apology
    - Returns final response

    Args:
        state: Current conversation state

    Returns:
        Updated state with final response
    """
    start_time = time.time()
    state.current_node = "return_response"
    state.execution_path.append("return_response")

    try:
        # Determine final response in English
        if state.should_escalate:
            # Use transfer message if available
            if state.transfer_message:
                english_response = state.transfer_message
            else:
                english_response = (
                    f"{state.generated_response}\n\n"
                    "I'm escalating this to a human agent who will be able to assist you better."
                )
            state.response_metadata["escalated"] = True
        else:
            english_response = state.generated_response
            state.response_metadata["escalated"] = False

        # Store original English response
        state.original_response = english_response

        # Translate response back to customer's language if not English
        if state.detected_language and state.detected_language != "en":
            translator = TranslationService()
            translation_result = translator.translate_from_english(
                text=english_response,
                target_language=state.detected_language,
            )

            if translation_result.success:
                state.translated_response = translation_result.translated_text
                state.translation_success = True
                state.translation_time_ms = translation_result.translation_time_ms
                final_response = state.translated_response
                logger.info(
                    f"Response translated to {state.language_name}: en -> {state.detected_language}, "
                    f"time: {translation_result.translation_time_ms:.2f}ms"
                )
            else:
                # Translation failed, use apology + English response
                state.translated_response = translator.handle_translation_failure(
                    original_response=english_response,
                    customer_language=state.detected_language,
                )
                state.translation_success = False
                state.translation_error = translation_result.error
                state.translation_time_ms = translation_result.translation_time_ms
                final_response = state.translated_response
                logger.warning(
                    f"Response translation failed: {translation_result.error}, "
                    f"using apology + English response"
                )
        else:
            # Already in English, no translation needed
            state.translated_response = english_response
            state.translation_success = True
            state.translation_time_ms = 0.0
            final_response = english_response

        state.final_response = final_response

        # Record intermediate result
        state.intermediate_results["return_response"] = {
            "final_response": final_response,
            "original_response": state.original_response,
            "translated_response": state.translated_response,
            "escalated": state.should_escalate,
            "translation_success": state.translation_success,
            "translation_time_ms": state.translation_time_ms,
            "customer_language": state.detected_language,
        }

        logger.info(
            f"Final response: {final_response[:50]}..., "
            f"translated: {state.translated_response != state.original_response}, "
            f"language: {state.detected_language}"
        )

    except Exception as e:
        state.error = str(e)
        state.failed_node = "return_response"
        logger.exception(f"Error in return_response node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["return_response"] = duration
        logger.debug(f"return_response node completed in {duration:.2f}s")

    return state


async def error_handling_node(state: ConversationState) -> ConversationState:
    """
    Error Handling Node: Handles errors that occurred during processing.

    This node:
    - Logs the error
    - Provides fallback response
    - Returns error state

    Args:
        state: Current conversation state

    Returns:
        Updated state with error response
    """
    start_time = time.time()
    state.current_node = "error_handling"
    state.execution_path.append("error_handling")

    try:
        # Provide fallback response
        fallback_response = "I apologize, but I encountered an error processing your request. Please try again or contact support if the issue persists."

        state.final_response = fallback_response
        state.response_metadata["error"] = True
        state.response_metadata["error_message"] = state.error
        state.response_metadata["failed_node"] = state.failed_node

        logger.error(f"Error handling: {state.error} (failed at: {state.failed_node})")

    except Exception as e:
        logger.exception(f"Error in error_handling node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["error_handling"] = duration
        logger.debug(f"error_handling node completed in {duration:.2f}s")

    return state
