"""LangGraph node specifications for conversation flow."""

import logging
import time
from typing import Any

from app.core.redis import get_queue_redis_client
from app.services.langgraph.context_manager import ContextManager
from app.services.langgraph.customer_profile import CustomerProfileService
from app.services.langgraph.intent_classifier import IntentClassifier
from app.services.langgraph.message_processor import (
    calculate_queue_priority,
    check_duplicate_message,
    detect_message_type,
    extract_message_metadata,
    generate_message_hash,
    sanitize_message,
    validate_message_length,
)
from app.services.langgraph.state import ConversationState

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
    Language Detection Node: Detects the language of the user message.

    This node:
    - Detects language from message
    - Returns language code and confidence
    - Handles edge cases (empty messages, unknown languages)

    Args:
        state: Current conversation state

    Returns:
        Updated state with detected language
    """
    start_time = time.time()
    state.current_node = "language_detection"
    state.execution_path.append("language_detection")

    try:
        # Simple language detection (in production, use a proper library like langdetect)
        # For now, we'll use a simple heuristic
        message = state.message.lower()

        # Simple language detection based on common words
        if any(word in message for word in ["hello", "hi", "help", "please", "thank"]):
            detected_lang = "en"
            confidence = 0.9
        elif any(word in message for word in ["hola", "gracias", "por favor"]):
            detected_lang = "es"
            confidence = 0.85
        elif any(word in message for word in ["bonjour", "merci", "s'il vous plaît"]):
            detected_lang = "fr"
            confidence = 0.85
        else:
            # Default to English
            detected_lang = "en"
            confidence = 0.5

        state.detected_language = detected_lang
        state.language_confidence = confidence

        # Record intermediate result
        state.intermediate_results["language_detection"] = {
            "detected_language": detected_lang,
            "confidence": confidence,
        }

        logger.info(f"Detected language: {detected_lang} (confidence: {confidence})")

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

        # Classify the intent
        classification_result = classifier.classify(state.message)

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
        # Construct search query
        search_query = state.message
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

        state.generated_response = generated_response
        state.response_source = "ai" if not state.search_results else "knowledge"

        # Record intermediate result
        state.intermediate_results["response_generation"] = {
            "generated_response": generated_response,
            "source": state.response_source,
        }

        logger.info(f"Generated response: {generated_response[:50]}...")

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
        message = state.message.lower()

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
    Return Response Node: Finalizes and returns the response.

    This node:
    - Selects appropriate response
    - Adds escalation message if needed
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
        # Determine final response
        if state.should_escalate:
            final_response = (
                f"{state.generated_response}\n\n"
                "I'm escalating this to a human agent who will be able to assist you better."
            )
            state.response_metadata["escalated"] = True
        else:
            final_response = state.generated_response
            state.response_metadata["escalated"] = False

        state.final_response = final_response

        # Record intermediate result
        state.intermediate_results["return_response"] = {
            "final_response": final_response,
            "escalated": state.should_escalate,
        }

        logger.info(f"Final response: {final_response[:50]}...")

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
