from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """Cached user profile for an active session."""

    user_id: UUID
    email: str
    name: str
    customer_type: str = "regular"
    language: str = "en"


class SessionData(BaseModel):
    """
    Redis session payload.
    Key pattern: session:{user_id}:{session_id}
  """

    session_id: UUID
    user_context: UserContext
    last_activity: datetime
    permissions: list[str] = Field(default_factory=list)
