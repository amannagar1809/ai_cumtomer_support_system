"""LangGraph workflow definition for conversation flow."""

import logging
from typing import Any

from app.services.langgraph.edges import (
    should_continue_after_escalation_decision,
    should_continue_after_error_handling,
    should_continue_after_intent_detection,
    should_continue_after_knowledge_search,
    should_continue_after_language_detection,
    should_continue_after_receive_query,
    should_continue_after_response_generation,
    should_continue_after_return_response,
    should_continue_after_sentiment_analysis,
)
from app.services.langgraph.nodes import (
    escalation_decision_node,
    error_handling_node,
    intent_detection_node,
    knowledge_search_node,
    language_detection_node,
    receive_query_node,
    response_generation_node,
    return_response_node,
    sentiment_analysis_node,
)
from app.services.langgraph.state import ConversationState

logger = logging.getLogger(__name__)


class ConversationWorkflow:
    """LangGraph workflow for conversation processing."""

    def __init__(self):
        self.nodes = {
            "receive_query": receive_query_node,
            "language_detection": language_detection_node,
            "intent_detection": intent_detection_node,
            "knowledge_search": knowledge_search_node,
            "sentiment_analysis": sentiment_analysis_node,
            "escalation_decision": escalation_decision_node,
            "response_generation": response_generation_node,
            "return_response": return_response_node,
            "error_handling": error_handling_node,
        }

        self.edges = {
            "receive_query": should_continue_after_receive_query,
            "language_detection": should_continue_after_language_detection,
            "intent_detection": should_continue_after_intent_detection,
            "knowledge_search": should_continue_after_knowledge_search,
            "sentiment_analysis": should_continue_after_sentiment_analysis,
            "escalation_decision": should_continue_after_escalation_decision,
            "response_generation": should_continue_after_response_generation,
            "return_response": should_continue_after_return_response,
            "error_handling": should_continue_after_error_handling,
        }

        self.entry_point = "receive_query"

    async def execute(self, initial_state: ConversationState) -> ConversationState:
        """
        Execute the conversation workflow.

        Args:
            initial_state: Initial conversation state

        Returns:
            Final conversation state
        """
        current_node = self.entry_point
        state = initial_state

        logger.info(f"Starting workflow execution for conversation {state.conversation_id}")

        while current_node != "__end__":
            try:
                # Execute current node
                node_func = self.nodes[current_node]
                state = await node_func(state)

                # Get next node from edge
                edge_func = self.edges[current_node]
                current_node = edge_func(state)

                logger.debug(f"Transitioned from {state.current_node} to {current_node}")

            except Exception as e:
                logger.exception(f"Error executing node {current_node}: {e}")
                state.error = str(e)
                state.failed_node = current_node
                current_node = "error_handling"

        logger.info(f"Workflow execution completed for conversation {state.conversation_id}")
        return state

    def get_workflow_graph(self) -> dict[str, Any]:
        """
        Get the workflow graph structure for visualization.

        Returns:
            Dictionary representing the workflow graph
        """
        return {
            "nodes": list(self.nodes.keys()),
            "edges": {
                node: edge_func.__name__
                for node, edge_func in self.edges.items()
            },
            "entry_point": self.entry_point,
        }

    def get_node_info(self, node_name: str) -> dict[str, Any]:
        """
        Get information about a specific node.

        Args:
            node_name: Name of the node

        Returns:
            Node information
        """
        if node_name not in self.nodes:
            return {"error": "Node not found"}

        return {
            "name": node_name,
            "function": self.nodes[node_name].__name__,
            "next_edge": self.edges[node_name].__name__,
        }

    def get_all_nodes_info(self) -> dict[str, dict[str, Any]]:
        """
        Get information about all nodes.

        Returns:
            Dictionary of node information
        """
        return {
            node_name: self.get_node_info(node_name)
            for node_name in self.nodes.keys()
        }
