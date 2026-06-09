import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat_ws import ChatWsEvent
from app.services.chat_session import anonymous_email
from app.services.chat_websocket import get_chat_connection_manager
from app.services.session_cache import SessionCacheService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authorize_chat_socket(
    conversation_id: UUID,
    session_id: UUID,
    anonymous_user_id: UUID,
) -> bool:
    user_id = None
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == anonymous_email(anonymous_user_id)),
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user_id = user.id

        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            ),
        )
        if conv_result.scalar_one_or_none() is None:
            return False

    session = await SessionCacheService().get(user_id, session_id)
    return session is not None and session.conversation_id == conversation_id


@router.websocket("/ws/v1/chat")
async def chat_websocket(
    websocket: WebSocket,
    conversation_id: UUID,
    session_id: UUID,
    anonymous_user_id: UUID,
) -> None:
    manager = get_chat_connection_manager()

    if not await _authorize_chat_socket(
        conversation_id,
        session_id,
        anonymous_user_id,
    ):
        await websocket.close(code=4403, reason="Unauthorized")
        return

    await manager.connect(websocket, conversation_id)

    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_client_message(websocket, conversation_id, data)
    except WebSocketDisconnect:
        logger.debug("Chat WebSocket disconnected for conversation %s", conversation_id)
    except Exception:
        logger.exception("Chat WebSocket error for conversation %s", conversation_id)
        await manager.send_to(
            websocket,
            ChatWsEvent(
                event="error",
                conversation_id=conversation_id,
                payload={"message": "Connection error"},
            ),
        )
    finally:
        await manager.disconnect(websocket, conversation_id)
