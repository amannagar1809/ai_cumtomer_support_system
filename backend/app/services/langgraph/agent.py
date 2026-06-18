"""LangGraph agent service for workflow execution."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.langgraph.checkpoint import CheckpointManager
from app.services.langgraph.state import ConversationState
from app.services.langgraph.workflow import ConversationWorkflow

logger = logging.getLogger(__name__)


class LangGraphAgent:
    """Agent service for executing LangGraph workflows."""

    def __init__(self):
        self.workflow = ConversationWorkflow()
        self.checkpoint_manager = CheckpointManager()

    async def process_message(
        self,
        message: str,
        conversation_id: UUID,
        user_id: UUID,
        channel: str = "web",
        metadata: dict[str, Any] | None = None,
        resume_from_checkpoint: bool = False,
    ) -> ConversationState:
        """
        Process a message through the LangGraph workflow.

        Args:
            message: User message
            conversation_id: Conversation ID
            user_id: User ID
            channel: Communication channel
            metadata: Channel-specific metadata
            resume_from_checkpoint: Whether to resume from latest checkpoint

        Returns:
            Final conversation state
        """
        try:
            # Try to resume from checkpoint if requested
            if resume_from_checkpoint:
                state = await self.checkpoint_manager.resume_from_checkpoint(str(conversation_id))
                if state:
                    # Update with new message
                    state.message = message
                    state.timestamp = datetime.utcnow()
                    logger.info(f"Resumed from checkpoint for conversation {conversation_id}")
                else:
                    # Create new state
                    state = ConversationState(
                        message=message,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        channel=channel,
                        metadata=metadata or {},
                    )
            else:
                # Create new state
                state = ConversationState(
                    message=message,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    channel=channel,
                    metadata=metadata or {},
                )

            # Execute workflow
            final_state = await self.workflow.execute(state)

            # Create checkpoint for final state
            await self.checkpoint_manager.create_checkpoint(final_state)

            return final_state

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            raise

    async def get_workflow_graph(self) -> dict[str, Any]:
        """
        Get the workflow graph structure.

        Returns:
            Workflow graph dictionary
        """
        return self.workflow.get_workflow_graph()

    async def get_node_info(self, node_name: str) -> dict[str, Any]:
        """
        Get information about a specific node.

        Args:
            node_name: Name of the node

        Returns:
            Node information
        """
        return self.workflow.get_node_info(node_name)

    async def get_all_nodes_info(self) -> dict[str, dict[str, Any]]:
        """
        Get information about all nodes.

        Returns:
            Dictionary of node information
        """
        return self.workflow.get_all_nodes_info()

    async def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Get a checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Checkpoint data or None
        """
        return await self.checkpoint_manager.get_checkpoint(checkpoint_id)

    async def get_latest_checkpoint(self, conversation_id: str) -> dict[str, Any] | None:
        """
        Get the latest checkpoint for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Checkpoint data or None
        """
        return await self.checkpoint_manager.get_latest_checkpoint(conversation_id)

    async def resume_from_checkpoint(
        self,
        conversation_id: str,
        from_node: str | None = None,
    ) -> ConversationState | None:
        """
        Resume execution from a checkpoint.

        Args:
            conversation_id: Conversation ID
            from_node: Optional node to resume from

        Returns:
            Restored state or None
        """
        return await self.checkpoint_manager.resume_from_checkpoint(conversation_id, from_node)

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """
        Clean up old checkpoints.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of checkpoints cleaned up
        """
        return await self.checkpoint_manager.cleanup_old_checkpoints(max_age_hours)
