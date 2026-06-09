from datetime import UTC, datetime
from uuid import UUID

from app.schemas.upload import LangGraphAttachmentPayload, MessageAttachment
from app.schemas.queue import AnalyticsEvent
from app.services.message_queue import MessageQueueService


class LangGraphAttachmentService:
    """
    Forward uploaded file URLs to the orchestrator pipeline.
    Images and PDFs are flagged for OCR in downstream LangGraph processing.
    """

    def __init__(self) -> None:
        self._queue = MessageQueueService()

    def _ocr_requested(self, attachment: MessageAttachment) -> MessageAttachment:
        needs_ocr = attachment.attachment_type.value in {"image", "pdf"}
        return attachment.model_copy(update={"ocr_requested": needs_ocr})

    async def submit_for_processing(
        self,
        *,
        conversation_id: UUID,
        message_id: UUID | None,
        attachments: list[MessageAttachment],
    ) -> LangGraphAttachmentPayload:
        enriched = [self._ocr_requested(a) for a in attachments]
        payload = LangGraphAttachmentPayload(
            conversation_id=conversation_id,
            message_id=message_id,
            attachments=enriched,
            queued_at=datetime.now(UTC),
        )
        await self._queue.publish_analytics(
            AnalyticsEvent(
                event_type="attachment.process",
                conversation_id=str(conversation_id),
                properties={
                    "message_id": str(message_id) if message_id else None,
                    "attachments": [a.model_dump(mode="json") for a in enriched],
                    "langgraph_handoff": True,
                    "ocr_required": any(a.ocr_requested for a in enriched),
                },
            ),
            correlation_id=str(conversation_id),
        )
        return payload
