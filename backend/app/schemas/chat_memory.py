from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChatMemoryRole(str, Enum):
    customer = "customer"
    ai = "ai"
    human_agent = "human_agent"


class ChatMemoryMessage(BaseModel):
    role: ChatMemoryRole
    content: str
    timestamp: datetime


class ChatMemoryState(BaseModel):
    """In-memory conversation transcript stored at chat_memory:{conversation_id}:messages."""

    conversation_id: str
    messages: list[ChatMemoryMessage] = Field(default_factory=list)
