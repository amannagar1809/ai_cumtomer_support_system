from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_client_ip
from app.schemas.chat import (
    ChatSessionResponse,
    ChatSessionStatusResponse,
    ContinueConversationRequest,
    ContinueConversationResponse,
    ConversationMessagesResponse,
    CreateChatSessionRequest,
    RedactMessageRequest,
    RedactMessageResponse,
    ReturningUserResponse,
    SendMessageRequest,
    SendMessageResponse,
    TransferSessionRequest,
    TransferSessionResponse,
)
from app.schemas.session import SessionMetadata
from app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/chat", tags=["chat"])


def session_metadata_from_request(
    request: Request,
    authenticated_user_id: UUID | None = None,
) -> SessionMetadata:
    return SessionMetadata(
        user_agent=request.headers.get("User-Agent"),
        ip_address=get_client_ip(request),
        referrer_url=request.headers.get("Referer"),
        authenticated_user_id=authenticated_user_id,
        is_authenticated=authenticated_user_id is not None,
    )


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume an anonymous chat session",
)
async def create_chat_session(
    body: CreateChatSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    service = ChatSessionService()
    return await service.start_session(
        db,
        body,
        session_metadata_from_request(request, body.authenticated_user_id),
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionStatusResponse,
    summary="Get anonymous chat session status",
)
async def get_chat_session(
    session_id: UUID,
    anonymous_user_id: UUID,
    authenticated_user_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionStatusResponse:
    service = ChatSessionService()
    session = await service.get_session_status(
        db,
        session_id,
        anonymous_user_id,
        authenticated_user_id,
    )
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
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ContinueConversationResponse:
    service = ChatSessionService()
    result = await service.continue_conversation(
        db,
        conversation_id,
        body.anonymous_user_id,
        body.authenticated_user_id,
        session_metadata_from_request(request, body.authenticated_user_id),
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this user",
        )
    return result


@router.post(
    "/sessions/{session_id}/transfer",
    response_model=TransferSessionResponse,
    summary="Transfer an anonymous chat session to an authenticated user",
)
async def transfer_session(
    session_id: UUID,
    body: TransferSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> TransferSessionResponse:
    service = ChatSessionService()
    result = await service.transfer_session(
        db,
        session_id,
        body.anonymous_user_id,
        body.authenticated_user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session or authenticated user not found",
        )
    return result


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/redact",
    response_model=RedactMessageResponse,
    summary="Redact a message for GDPR compliance",
)
async def redact_message(
    conversation_id: UUID,
    message_id: UUID,
    body: RedactMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> RedactMessageResponse:
    service = ChatSessionService()
    message = await service.redact_message(
        db,
        conversation_id,
        message_id,
        body.anonymous_user_id,
        body.reason,
        body.authenticated_user_id,
    )
    if message is None or message.redacted_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found for this conversation",
        )
    return RedactMessageResponse(
        message_id=message.id,
        conversation_id=message.conversation_id,
        redacted_at=message.redacted_at,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    summary="Fetch recent messages for a conversation",
)
async def get_conversation_messages(
    conversation_id: UUID,
    anonymous_user_id: UUID,
    authenticated_user_id: UUID | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> ConversationMessagesResponse:
    _ = limit  # service uses configured default; reserved for future override
    service = ChatSessionService()
    result = await service.get_conversation_messages(
        db,
        conversation_id,
        anonymous_user_id,
        authenticated_user_id,
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
    try:
        result = await service.send_message(
            db,
            conversation_id,
            body.anonymous_user_id,
            body.content,
            authenticated_user_id=body.authenticated_user_id,
            session_id=body.session_id,
            attachments=body.attachments,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this user",
        )
    return result
