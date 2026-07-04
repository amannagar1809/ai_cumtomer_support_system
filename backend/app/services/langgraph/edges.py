"""LangGraph conditional edges for conversation flow."""

from typing import Literal

from app.services.langgraph.state import ConversationState


def should_continue_after_receive_query(state: ConversationState) -> Literal["language_detection", "error_handling"]:
    """
    Conditional edge after Receive Query node.

    Determines whether to proceed to Language Detection or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "language_detection"


def should_continue_after_language_detection(state: ConversationState) -> Literal["intent_detection", "error_handling"]:
    """
    Conditional edge after Language Detection node.

    Determines whether to proceed to Intent Detection or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "intent_detection"


def should_continue_after_intent_detection(state: ConversationState) -> Literal["knowledge_search", "error_handling"]:
    """
    Conditional edge after Intent Detection node.

    Determines whether to proceed to Knowledge Search or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "knowledge_search"


def should_continue_after_knowledge_search(state: ConversationState) -> Literal["response_generation", "error_handling"]:
    """
    Conditional edge after Knowledge Search node.

    Determines whether to proceed to Response Generation or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "response_generation"


def should_continue_after_response_generation(state: ConversationState) -> Literal["sentiment_analysis", "error_handling"]:
    """
    Conditional edge after Response Generation node.

    Determines whether to proceed to Sentiment Analysis or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "sentiment_analysis"


def should_continue_after_sentiment_analysis(state: ConversationState) -> Literal["escalation_decision", "error_handling"]:
    """
    Conditional edge after Sentiment Analysis node.

    Determines whether to proceed to Escalation Decision or Error Handling.
    """
    if state.error:
        return "error_handling"
    return "escalation_decision"


def should_continue_after_escalation_decision(state: ConversationState) -> Literal["response_generation", "return_response", "error_handling"]:
    """
    Conditional edge after Escalation Decision node.

    If escalated, skip Response Generation and go to Return Response (with handoff data).
    If not escalated, proceed to Response Generation.
    """
    if state.error:
        return "error_handling"
    
    # If escalated, skip response generation and go directly to return_response
    # The return_response node will handle the handoff data
    if state.should_escalate:
        return "return_response"
    
    # If not escalated, proceed to response generation
    return "response_generation"


def should_continue_after_return_response(state: ConversationState) -> Literal["__end__"]:
    """
    Conditional edge after Return Response node.

    Always ends the workflow.
    """
    return "__end__"


def should_continue_after_error_handling(state: ConversationState) -> Literal["__end__"]:
    """
    Conditional edge after Error Handling node.

    Always ends the workflow.
    """
    return "__end__"
