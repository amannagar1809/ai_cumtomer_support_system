import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.chat_ws import ChatWsEvent
from app.services.chat_websocket import get_chat_connection_manager

logger = logging.getLogger(__name__)


class AiResponseService:
    """Simulated AI processing with typing indicator WebSocket events."""

    def schedule(
        self,
        conversation_id: UUID,
        customer_message: str,
    ) -> None:
        asyncio.create_task(
            self._process(conversation_id, customer_message),
            name=f"ai-response-{conversation_id}",
        )

    async def _process(
        self,
        conversation_id: UUID,
        customer_message: str,
    ) -> None:
        ws = get_chat_connection_manager()
        delay = settings.chat_ai_processing_delay_seconds
        still_after = settings.chat_typing_still_working_after_seconds

        try:
            await ws.broadcast(
                conversation_id,
                ChatWsEvent(event="typing_start", conversation_id=conversation_id),
            )

            started = time.monotonic()
            still_sent = False
            elapsed = 0.0
            while elapsed < delay:
                await asyncio.sleep(0.25)
                elapsed = time.monotonic() - started
                if not still_sent and elapsed >= still_after:
                    await ws.broadcast(
                        conversation_id,
                        ChatWsEvent(
                            event="still_working",
                            conversation_id=conversation_id,
                            payload={"message": "Still working on your request..."},
                        ),
                    )
                    still_sent = True

            reply = self._build_reply(customer_message)
            timestamp = datetime.now(UTC)

            async with AsyncSessionLocal() as db:
                from app.services.chat_session import ChatSessionService

                service = ChatSessionService()
                row = await service.persist_ai_reply(db, conversation_id, reply)
                await db.commit()
                message_id = str(row.id)

            await ws.broadcast(
                conversation_id,
                ChatWsEvent(
                    event="message",
                    conversation_id=conversation_id,
                    payload={
                        "role": "ai",
                        "content": reply,
                        "timestamp": timestamp.isoformat(),
                        "message_id": message_id,
                    },
                ),
            )
        except Exception:
            logger.exception(
                "AI response processing failed for conversation %s",
                conversation_id,
            )
        finally:
            await ws.broadcast(
                conversation_id,
                ChatWsEvent(event="typing_stop", conversation_id=conversation_id),
            )

    def _build_reply(self, customer_message: str) -> str:
        text = customer_message.strip().lower()
        if not text:
            return (
                "Thanks for sharing those files. I am reviewing them and will "
                "follow up with next steps shortly."
            )
        if any(word in text for word in ("refund", "billing", "charge", "payment")):
            return (
                "I understand you have a billing concern. I am checking your account "
                "details now and will share an update in a moment."
            )
        if any(word in text for word in ("broken", "error", "not working", "bug")):
            return (
                "Sorry you are running into this issue. I am looking into possible "
                "causes and will suggest a fix shortly."
            )
        return (
            "Thanks for your message. I am working on the best answer for you "
            "and will respond here as soon as it is ready."
        )
