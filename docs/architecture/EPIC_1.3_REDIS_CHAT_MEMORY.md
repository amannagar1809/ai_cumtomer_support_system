# Epic 1.3 — Redis Chat Memory

**User Story 1.3.1** (chat memory) · AI Customer Support System

---

## 1. Scope

| Task | Status |
|------|--------|
| Separate Redis database `db=1` for chat memory | ✅ |
| Memory TTL 30 minutes (active conversations) | ✅ |
| Key pattern `chat_memory:{conversation_id}:messages` | ✅ |
| Sliding window expiration (TTL reset on each message) | ✅ |

---

## 2. Redis database separation

| Purpose | DB | URL env var | Default |
|---------|----|-------------|---------|
| Sessions, general cache | **0** | `REDIS_URL` | `redis://localhost:6379/0` |
| Chat memory (transcripts) | **1** | `REDIS_CHAT_MEMORY_URL` | `redis://localhost:6379/1` |

Same Redis instance, logical isolation via database index.

---

## 3. TTL — 30 minutes (sliding window)

| Setting | Value |
|---------|-------|
| `REDIS_CHAT_MEMORY_TTL_SECONDS` | `1800` (30 min) |

**Sliding window behavior:**

1. User sends message → `RPUSH` + `EXPIRE 1800`
2. Each new message → **TTL reset to 30 minutes**
3. No activity for 30 min → key expires, memory cleared
4. `touch()` can extend TTL without a new message (optional heartbeat)

---

## 4. Key pattern

```
chat_memory:{conversation_id}:messages
```

**Type:** Redis `LIST` (ordered messages, oldest → newest)

**Example:**

```
chat_memory:7c9e6679-7425-40de-944b-e07fc1f90ae7:messages
```

---

## 5. Message structure

**Schema:** `backend/app/schemas/chat_memory.py`

Each list item (JSON):

```json
{
  "role": "customer",
  "content": "I need help with my order",
  "timestamp": "2026-06-02T10:15:00Z"
}
```

| `role` | Values |
|--------|--------|
| | `customer`, `ai`, `human_agent` |

---

## 6. Service API

**File:** `backend/app/services/chat_memory.py`

| Method | Description |
|--------|-------------|
| `append_message(conversation_id, message)` | Add message + **reset TTL** (sliding window) |
| `get_messages(conversation_id)` | Return full transcript |
| `touch(conversation_id)` | Extend TTL only |
| `ttl_seconds(conversation_id)` | Remaining seconds |
| `clear(conversation_id)` | Delete memory |

**Usage:**

```python
from datetime import UTC, datetime
from uuid import UUID

from app.schemas.chat_memory import ChatMemoryMessage, ChatMemoryRole
from app.services.chat_memory import ChatMemoryService

service = ChatMemoryService()
conv_id = UUID("...")

await service.append_message(
    conv_id,
    ChatMemoryMessage(
        role=ChatMemoryRole.customer,
        content="Hello",
        timestamp=datetime.now(UTC),
    ),
)
state = await service.get_messages(conv_id)
```

---

## 7. Wiring

| Component | Path |
|-----------|------|
| Chat memory Redis client | `get_chat_memory_redis_client()` in `app/core/redis.py` |
| Settings | `redis_chat_memory_url`, `redis_chat_memory_ttl_seconds` |
| Service | `app/services/chat_memory.py` |

---

## 8. Verify locally

```bash
docker compose up -d redis
```

```bash
docker exec ai_support_redis redis-cli -n 1 PING
```

After app writes a message, inspect:

```bash
docker exec ai_support_redis redis-cli -n 1 KEYS "chat_memory:*"
docker exec ai_support_redis redis-cli -n 1 TTL "chat_memory:<uuid>:messages"
```

---

## 9. Acceptance checklist

| Requirement | Done |
|-------------|------|
| Redis `db=1` for chat memory | ✅ |
| TTL 30 minutes | ✅ |
| Key `chat_memory:{conversation_id}:messages` | ✅ |
| Sliding window on new message | ✅ |
