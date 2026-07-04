"""LangGraph checkpoint mechanism for resuming from any node."""

import json
import logging
from datetime import datetime
from typing import Any

from app.core.redis import get_redis_client
from app.services.langgraph.state import ConversationState

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manager for creating and restoring checkpoints."""

    def __init__(self):
        self.redis_prefix = "langgraph_checkpoint"
        self.checkpoint_ttl = 3600  # 1 hour

    async def create_checkpoint(self, state: ConversationState) -> str:
        """
        Create a checkpoint for the current state.

        Args:
            state: Current conversation state

        Returns:
            Checkpoint ID
        """
        redis = await get_redis_client()

        try:
            checkpoint_id = f"{state.conversation_id}_{state.current_node}_{int(datetime.utcnow().timestamp())}"

            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "state": state.model_dump(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            key = f"{self.redis_prefix}:{checkpoint_id}"
            await redis.setex(key, self.checkpoint_ttl, json.dumps(checkpoint_data))

            # Also store the latest checkpoint for the conversation
            latest_key = f"{self.redis_prefix}:latest:{state.conversation_id}"
            await redis.setex(latest_key, self.checkpoint_ttl, checkpoint_id)

            logger.info(f"Created checkpoint {checkpoint_id} for conversation {state.conversation_id}")
            return checkpoint_id

        except Exception as e:
            logger.exception(f"Error creating checkpoint: {e}")
            raise

    async def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Retrieve a checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Checkpoint data or None
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{checkpoint_id}"
            checkpoint_json = await redis.get(key)

            if not checkpoint_json:
                return None

            return json.loads(checkpoint_json)

        except Exception as e:
            logger.exception(f"Error retrieving checkpoint: {e}")
            return None

    async def get_latest_checkpoint(self, conversation_id: str) -> dict[str, Any] | None:
        """
        Retrieve the latest checkpoint for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Checkpoint data or None
        """
        redis = await get_redis_client()

        try:
            latest_key = f"{self.redis_prefix}:latest:{conversation_id}"
            checkpoint_id = await redis.get(latest_key)

            if not checkpoint_id:
                return None

            return await self.get_checkpoint(checkpoint_id.decode())

        except Exception as e:
            logger.exception(f"Error retrieving latest checkpoint: {e}")
            return None

    async def restore_state(self, checkpoint_id: str) -> ConversationState | None:
        """
        Restore state from a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Restored state or None
        """
        checkpoint_data = await self.get_checkpoint(checkpoint_id)

        if not checkpoint_data:
            return None

        try:
            state_data = checkpoint_data["state"]
            state = ConversationState(**state_data)
            logger.info(f"Restored state from checkpoint {checkpoint_id}")
            return state

        except Exception as e:
            logger.exception(f"Error restoring state from checkpoint: {e}")
            return None

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            True if deleted successfully
        """
        redis = await get_redis_client()

        try:
            key = f"{self.redis_prefix}:{checkpoint_id}"
            await redis.delete(key)
            logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True

        except Exception as e:
            logger.exception(f"Error deleting checkpoint: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """
        Clean up old checkpoints.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of checkpoints cleaned up
        """
        redis = await get_redis_client()

        try:
            # Get all checkpoint keys
            pattern = f"{self.redis_prefix}:*"
            keys = await redis.keys(pattern)

            cleaned_count = 0
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)

            for key in keys:
                try:
                    # Skip latest checkpoint keys
                    if b":latest:" in key:
                        continue

                    checkpoint_json = await redis.get(key)
                    if not checkpoint_json:
                        continue

                    checkpoint_data = json.loads(checkpoint_json)
                    timestamp = datetime.fromisoformat(checkpoint_data["timestamp"])

                    if timestamp.timestamp() < cutoff_time:
                        await redis.delete(key)
                        cleaned_count += 1

                except Exception as e:
                    logger.warning(f"Error processing checkpoint key {key}: {e}")

            logger.info(f"Cleaned up {cleaned_count} old checkpoints")
            return cleaned_count

        except Exception as e:
            logger.exception(f"Error cleaning up old checkpoints: {e}")
            return 0

    async def resume_from_checkpoint(self, conversation_id: str, from_node: str | None = None) -> ConversationState | None:
        """
        Resume execution from a checkpoint.

        Args:
            conversation_id: Conversation ID
            from_node: Optional node to resume from (if None, resumes from latest)

        Returns:
            Restored state or None
        """
        if from_node:
            # Find checkpoint for specific node
            # This would require scanning checkpoints, for now use latest
            checkpoint_data = await self.get_latest_checkpoint(conversation_id)
        else:
            checkpoint_data = await self.get_latest_checkpoint(conversation_id)

        if not checkpoint_data:
            return None

        state = await self.restore_state(checkpoint_data["checkpoint_id"])

        if state and from_node:
            # Reset execution path to resume from specific node
            if from_node in state.execution_path:
                index = state.execution_path.index(from_node)
                state.execution_path = state.execution_path[:index + 1]
                state.current_node = from_node

        return state
