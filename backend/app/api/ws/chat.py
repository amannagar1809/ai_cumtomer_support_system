import logging
from uuid import UUID

from fastapi import APIRouter, Header, Query, WebSocket, WebSocketDisconnect
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
    session_id: UUID | None,
    anonymous_user_id: UUID,
) -> bool:
    if session_id is None:
        return False

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


def _session_id_from_token(
    session_id: UUID | None,
    token: str | None,
    authorization: str | None,
) -> UUID | None:
    raw = token
    if raw is None and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            raw = value
    if raw is None:
        return session_id
    try:
        return UUID(raw)
    except ValueError:
        return None


async def _serve_chat_websocket(
    websocket: WebSocket,
    conversation_id: UUID,
    session_id: UUID | None,
    anonymous_user_id: UUID,
    last_sequence: int | None,
    token: str | None = None,
    authorization: str | None = None,
) -> None:
    manager = get_chat_connection_manager()
    resolved_session_id = _session_id_from_token(session_id, token, authorization)

    if not await _authorize_chat_socket(
        conversation_id,
        resolved_session_id,
        anonymous_user_id,
    ):
        await websocket.close(code=4403, reason="Unauthorized")
        return

    connected = await manager.connect(
        websocket,
        conversation_id,
        last_sequence=last_sequence,
    )
    if not connected:
        return

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


@router.websocket("/ws/chat/{conversation_id}")
async def chat_websocket(
    websocket: WebSocket,
    conversation_id: UUID,
    anonymous_user_id: UUID,
    session_id: UUID | None = None,
    token: str | None = None,
    last_sequence: int | None = Query(default=None, ge=0),
    authorization: str | None = Header(default=None),
) -> None:
    await _serve_chat_websocket(
        websocket,
        conversation_id,
        session_id,
        anonymous_user_id,
        last_sequence,
        token,
        authorization,
    )


@router.websocket("/ws/v1/chat")
async def legacy_chat_websocket(
    websocket: WebSocket,
    conversation_id: UUID,
    session_id: UUID,
    anonymous_user_id: UUID,
    last_sequence: int | None = Query(default=None, ge=0),
) -> None:
    await _serve_chat_websocket(
        websocket,
        conversation_id,
        session_id,
        anonymous_user_id,
        last_sequence,
    )
