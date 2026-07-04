import json
from uuid import UUID

from pydantic import BaseModel, Field


class SentimentPoint(BaseModel):
    label: str
    score: float


class UserContextCache(BaseModel):
    """
    Redis HASH at user_context:{user_id}
    Fields: preferred_language, last_conversation_id, sentiment_trend, active_ticket_ids
    """

    user_id: UUID
    preferred_language: str = "en"
    last_conversation_id: UUID | None = None
    sentiment_trend: list[SentimentPoint] = Field(default_factory=list)
    active_ticket_ids: list[UUID] = Field(default_factory=list)

    def to_redis_hash(self) -> dict[str, str]:
        return {
            "preferred_language": self.preferred_language,
            "last_conversation_id": (
                str(self.last_conversation_id) if self.last_conversation_id else ""
            ),
            "sentiment_trend": json.dumps(
                [p.model_dump() for p in self.sentiment_trend]
            ),
            "active_ticket_ids": json.dumps(
                [str(tid) for tid in self.active_ticket_ids]
            ),
        }

    @classmethod
    def from_redis_hash(cls, user_id: UUID, data: dict[str, str]) -> "UserContextCache":
        sentiment_raw = json.loads(data.get("sentiment_trend") or "[]")
        ticket_raw = json.loads(data.get("active_ticket_ids") or "[]")
        last_conv = data.get("last_conversation_id") or ""
        return cls(
            user_id=user_id,
            preferred_language=data.get("preferred_language") or "en",
            last_conversation_id=UUID(last_conv) if last_conv else None,
            sentiment_trend=[SentimentPoint.model_validate(s) for s in sentiment_raw],
            active_ticket_ids=[UUID(t) for t in ticket_raw],
        )
