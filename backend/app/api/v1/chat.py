from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.chat import (
    ChatSessionResponse,
    ChatSessionStatusResponse,
    ContinueConversationRequest,
    ContinueConversationResponse,
    ConversationMessagesResponse,
    CreateChatSessionRequest,
    ReturningUserResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume an anonymous chat session",
)
async def create_chat_session(
    body: CreateChatSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    service = ChatSessionService()
    return await service.start_session(db, body)


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionStatusResponse,
    summary="Get anonymous chat session status",
)
async def get_chat_session(
    session_id: UUID,
    anonymous_user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionStatusResponse:
    service = ChatSessionService()
    session = await service.get_session_status(db, session_id, anonymous_user_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )
    return session


@router.get(
    "/returning-user",
    response_model=ReturningUserResponse,
    summary="Detect returning anonymous user with a previous conversation",
)
async def get_returning_user(
    anonymous_user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ReturningUserResponse:
    service = ChatSessionService()
    return await service.get_returning_user_status(db, anonymous_user_id)


@router.post(
    "/conversations/{conversation_id}/continue",
    response_model=ContinueConversationResponse,
    summary="Continue a previous conversation",
)
async def continue_conversation(
    conversation_id: UUID,
    body: ContinueConversationRequest,
    db: AsyncSession = Depends(get_db),
) -> ContinueConversationResponse:
    service = ChatSessionService()
    result = await service.continue_conversation(
        db,
        conversation_id,
        body.anonymous_user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this user",
        )
    return result


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    summary="Fetch recent messages for a conversation",
)
async def get_conversation_messages(
    conversation_id: UUID,
    anonymous_user_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> ConversationMessagesResponse:
    _ = limit  # service uses configured default; reserved for future override
    service = ChatSessionService()
    result = await service.get_conversation_messages(
        db,
        conversation_id,
        anonymous_user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this user",
        )
    return result


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a customer message",
)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    service = ChatSessionService()
    result = await service.send_message(
        db,
        conversation_id,
        body.anonymous_user_id,
        body.content,
        session_id=body.session_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this user",
        )
    return result
