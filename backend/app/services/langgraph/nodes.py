"""LangGraph node specifications for conversation flow."""

import logging
import time
from typing import Any

from app.services.langgraph.state import ConversationState

logger = logging.getLogger(__name__)

# Node timeout configuration (5 seconds per node max)
NODE_TIMEOUT = 5.0


async def receive_query_node(state: ConversationState) -> ConversationState:
    """
    Receive Query Node: Initial node that receives and validates the user query.

    This node:
    - Validates the input message
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
        # Validate message
        if not state.message or not state.message.strip():
            raise ValueError("Message cannot be empty")

        # Clean the message
        state.message = state.message.strip()

        # Record intermediate result
        state.intermediate_results["receive_query"] = {
            "validated": True,
            "message_length": len(state.message),
            "timestamp": state.timestamp.isoformat(),
        }

        # Create checkpoint
        state.checkpoint_id = f"checkpoint_{state.conversation_id}_{int(time.time())}"
        state.can_resume = True

        logger.info(f"Received query: {state.message[:50]}...")

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
    - Classifies the user's intent (e.g., support_request, complaint, question)
    - Extracts entities (e.g., product names, order IDs)
    - Returns intent classification with confidence

    Args:
        state: Current conversation state

    Returns:
        Updated state with detected intent
    """
    start_time = time.time()
    state.current_node = "intent_detection"
    state.execution_path.append("intent_detection")

    try:
        message = state.message.lower()

        # Simple intent detection (in production, use a proper NLP model)
        intent_keywords = {
            "support_request": ["help", "support", "assist", "problem"],
            "complaint": ["complain", "issue", "broken", "not working", "angry"],
            "question": ["what", "how", "why", "when", "where", "?"],
            "greeting": ["hello", "hi", "hey", "good morning", "good evening"],
            "farewell": ["bye", "goodbye", "see you", "thanks"],
        }

        detected_intent = "general"
        confidence = 0.5
        entities = {}

        for intent, keywords in intent_keywords.items():
            if any(keyword in message for keyword in keywords):
                detected_intent = intent
                confidence = 0.8
                break

        # Extract simple entities (e.g., order numbers)
        import re

        order_match = re.search(r"order\s*#?(\d+)", message)
        if order_match:
            entities["order_id"] = order_match.group(1)
            confidence += 0.1

        state.detected_intent = detected_intent
        state.intent_confidence = min(confidence, 1.0)
        state.intent_entities = entities

        # Record intermediate result
        state.intermediate_results["intent_detection"] = {
            "detected_intent": detected_intent,
            "confidence": state.intent_confidence,
            "entities": entities,
        }

        logger.info(f"Detected intent: {detected_intent} (confidence: {state.intent_confidence})")

    except Exception as e:
        state.error = str(e)
        state.failed_node = "intent_detection"
        logger.exception(f"Error in intent_detection node: {e}")

    finally:
        duration = time.time() - start_time
        state.node_durations["intent_detection"] = duration
        logger.debug(f"intent_detection node completed in {duration:.2f}s")

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
