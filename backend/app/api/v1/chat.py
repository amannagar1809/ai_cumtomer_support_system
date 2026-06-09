from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.chat import (
    ChatSessionResponse,
    ChatSessionStatusResponse,
    CreateChatSessionRequest,
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
    """
    Initialize anonymous chat without login.
    Client should send `anonymous_user_id` from localStorage on return visits
    to resume an active session when possible.
    """
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
