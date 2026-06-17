"""Mobile chat REST endpoints for apps that can't use WebSocket."""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_async_session
from app.models.conversation import Conversation, ConversationChannel
from app.models.message import Message
from app.models.user import User
from app.services.mobile_offline import MobileOfflineService
from app.schemas.mobile_chat import (
    MobileConversation,
    MobileConversationListResponse,
    MobileGetMessagesRequest,
    MobileGetMessagesResponse,
    MobileLongPollRequest,
    MobileLongPollResponse,
    MobileMessage,
    MobileSendMessageRequest,
    MobileSendMessageResponse,
    MobileSyncRequest,
    MobileSyncResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile-chat"])

# Initialize services
offline_service = MobileOfflineService()


@router.post("/conversations", response_model=MobileSendMessageResponse)
async def create_mobile_conversation(
    request: MobileSendMessageRequest,
    current_user: User = get_current_user(),
    background_tasks: BackgroundTasks = None,
) -> MobileSendMessageResponse:
    """
    Create a new conversation and send the first message via mobile chat.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    async for session in get_async_session():
        try:
            # Create new conversation
            conversation = Conversation(
                user_id=current_user.id,
                channel=ConversationChannel.web,
                status="active",
            )
            session.add(conversation)
            await session.flush()
            await session.refresh(conversation)

            # Create message
            message = Message(
                conversation_id=conversation.id,
                sender_type="customer",
                message=request.message,
                language="en",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            # Queue for AI processing
            background_tasks.add_task(
                _queue_message_for_processing,
                conversation.id,
                message.id,
                current_user.id,
                request.message,
            )

            return MobileSendMessageResponse(
                message_id=message.id,
                conversation_id=conversation.id,
                timestamp=message.timestamp,
                status="sent",
            )

        except Exception as e:
            logger.exception(f"Error creating mobile conversation: {e}")
            await session.rollback()
            raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.post("/conversations/{conversation_id}/messages", response_model=MobileSendMessageResponse)
async def send_mobile_message(
    conversation_id: UUID,
    request: MobileSendMessageRequest,
    current_user: User = get_current_user(),
    background_tasks: BackgroundTasks = None,
) -> MobileSendMessageResponse:
    """
    Send a message to an existing conversation via mobile chat.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    async for session in get_async_session():
        try:
            # Verify conversation exists and belongs to user
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                )
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Create message
            message = Message(
                conversation_id=conversation.id,
                sender_type="customer",
                message=request.message,
                language="en",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            # Queue for AI processing
            background_tasks.add_task(
                _queue_message_for_processing,
                conversation.id,
                message.id,
                current_user.id,
                request.message,
            )

            return MobileSendMessageResponse(
                message_id=message.id,
                conversation_id=conversation.id,
                timestamp=message.timestamp,
                status="sent",
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error sending mobile message: {e}")
            await session.rollback()
            raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/conversations/{conversation_id}/messages/poll", response_model=MobileLongPollResponse)
async def long_poll_messages(
    conversation_id: UUID,
    request: MobileLongPollRequest,
    current_user: User = get_current_user(),
) -> MobileLongPollResponse:
    """
    Long-poll for new messages in a conversation.
    This is a fallback for devices with poor network conditions.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    if not settings.mobile_long_polling_enabled:
        raise HTTPException(status_code=400, detail="Long-polling is not enabled")

    async for session in get_async_session():
        try:
            # Verify conversation exists and belongs to user
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                )
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Long-poll with timeout
            timeout = min(request.timeout, settings.mobile_long_polling_timeout)
            messages = []
            timeout_reached = True

            # Poll for new messages
            start_time = datetime.utcnow()
            while True:
                result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.timestamp.desc())
                    .limit(50)
                )
                db_messages = result.scalars().all()

                # Check if there are new messages
                if request.last_message_id:
                    new_messages = [
                        msg for msg in db_messages if msg.id != request.last_message_id
                    ]
                else:
                    new_messages = db_messages

                if new_messages:
                    messages = [
                        MobileMessage(
                            id=msg.id,
                            conversation_id=msg.conversation_id,
                            sender_type=msg.sender_type,
                            message=msg.message,
                            timestamp=msg.timestamp,
                            language=msg.language,
                            sentiment=msg.sentiment,
                            is_read=False,  # Will be updated based on read status
                        )
                        for msg in reversed(new_messages)
                    ]
                    timeout_reached = False
                    break

                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed >= timeout:
                    timeout_reached = True
                    break

                # Wait before next poll
                await asyncio.sleep(1)

            return MobileLongPollResponse(
                messages=messages,
                conversation_id=conversation_id,
                timeout_reached=timeout_reached,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in long-poll: {e}")
            raise HTTPException(status_code=500, detail="Failed to poll messages")


@router.post("/conversations/{conversation_id}/messages/get", response_model=MobileGetMessagesResponse)
async def get_messages(
    conversation_id: UUID,
    request: MobileGetMessagesRequest,
    current_user: User = get_current_user(),
) -> MobileGetMessagesResponse:
    """
    Get messages for a conversation with pagination.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    async for session in get_async_session():
        try:
            # Verify conversation exists and belongs to user
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                )
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Get messages
            query = select(Message).where(Message.conversation_id == conversation_id)

            if request.since:
                query = query.where(Message.timestamp >= request.since)

            query = query.order_by(Message.timestamp.desc()).offset(request.offset).limit(request.limit + 1)

            result = await session.execute(query)
            messages = result.scalars().all()

            # Check if there are more messages
            has_more = len(messages) > request.limit
            messages = messages[:request.limit]

            mobile_messages = [
                MobileMessage(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    sender_type=msg.sender_type,
                    message=msg.message,
                    timestamp=msg.timestamp,
                    language=msg.language,
                    sentiment=msg.sentiment,
                    is_read=False,
                )
                for msg in reversed(messages)
            ]

            last_timestamp = mobile_messages[-1].timestamp if mobile_messages else None

            return MobileGetMessagesResponse(
                messages=mobile_messages,
                conversation_id=conversation_id,
                has_more=has_more,
                last_timestamp=last_timestamp,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error getting messages: {e}")
            raise HTTPException(status_code=500, detail="Failed to get messages")


@router.get("/conversations", response_model=MobileConversationListResponse)
async def get_conversations(
    current_user: User = get_current_user(),
    limit: int = 20,
    offset: int = 0,
) -> MobileConversationListResponse:
    """
    Get list of conversations for the current user.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    async for session in get_async_session():
        try:
            # Get conversations
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == current_user.id)
                .order_by(Conversation.started_at.desc())
                .offset(offset)
                .limit(limit + 1)
            )
            conversations = result.scalars().all()

            # Check if there are more
            has_more = len(conversations) > limit
            conversations = conversations[:limit]

            # Get message counts
            mobile_conversations = []
            for conv in conversations:
                # Get message count
                msg_result = await session.execute(
                    select(Message).where(Message.conversation_id == conv.id)
                )
                messages = msg_result.scalars().all()

                mobile_conversations.append(
                    MobileConversation(
                        id=conv.id,
                        user_id=conv.user_id,
                        channel=conv.channel.value,
                        status=conv.status,
                        started_at=conv.started_at,
                        last_message_at=messages[-1].timestamp if messages else None,
                        message_count=len(messages),
                        unread_count=0,  # Would be calculated from read status
                    )
                )

            return MobileConversationListResponse(
                conversations=mobile_conversations,
                total=len(mobile_conversations),
                has_more=has_more,
            )

        except Exception as e:
            logger.exception(f"Error getting conversations: {e}")
            raise HTTPException(status_code=500, detail="Failed to get conversations")


async def _queue_message_for_processing(
    conversation_id: UUID,
    message_id: UUID,
    user_id: UUID,
    message: str,
) -> None:
    """Queue message for AI processing."""
    try:
        from app.services.message_queue import MessageQueueService

        queue = MessageQueueService()

        internal_message = {
            "conversation_id": str(conversation_id),
            "message_id": str(message_id),
            "user_id": str(user_id),
            "message": message,
            "sender_type": "customer",
            "channel": "mobile",
            "timestamp": datetime.utcnow().isoformat(),
        }

        await queue.add_to_queue("mobile_queue", internal_message)
        logger.info(f"Queued mobile message {message_id} for processing")

    except Exception as e:
        logger.exception(f"Error queuing mobile message: {e}")


@router.post("/sync", response_model=MobileSyncResponse)
async def sync_offline_messages(
    request: MobileSyncRequest,
    current_user: User = get_current_user(),
) -> MobileSyncResponse:
    """
    Sync offline messages from device to server.
    This endpoint handles message sync when connection is restored.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    if not settings.mobile_message_sync_enabled:
        raise HTTPException(status_code=400, detail="Message sync is not enabled")

    try:
        return await offline_service.sync_offline_messages(request, current_user.id)
    except Exception as e:
        logger.exception(f"Error syncing offline messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync messages")


@router.get("/devices/{device_id}/status")
async def get_device_status(
    device_id: str,
    current_user: User = get_current_user(),
) -> dict[str, Any]:
    """
    Get offline queue status for a device.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    try:
        return await offline_service.get_device_status(device_id)
    except Exception as e:
        logger.exception(f"Error getting device status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get device status")


@router.delete("/devices/{device_id}/offline")
async def clear_offline_messages(
    device_id: str,
    current_user: User = get_current_user(),
) -> dict[str, Any]:
    """
    Clear all offline messages for a device.
    """
    if not settings.mobile_chat_enabled:
        raise HTTPException(status_code=400, detail="Mobile chat is not enabled")

    try:
        count = await offline_service.clear_offline_messages(device_id)
        return {"device_id": device_id, "messages_cleared": count}
    except Exception as e:
        logger.exception(f"Error clearing offline messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear messages")
