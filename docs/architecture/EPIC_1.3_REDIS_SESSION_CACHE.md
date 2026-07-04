# Epic 1.3 — Redis Session Cache

**User Story 1.3.1** · AI Customer Support System

---

## 1. Scope

Session cache configuration for fast, ephemeral user sessions in Redis.

| Task | Status |
|------|--------|
| Redis `maxmemory` 2GB + LRU eviction | ✅ |
| Session TTL 24 hours | ✅ |
| Key pattern `session:{user_id}:{session_id}` | ✅ |
| Session data structure (context, activity, permissions) | ✅ |

---

## 2. Redis instance configuration

**File:** `backend/db/redis/redis.conf`

| Setting | Value |
|---------|-------|
| `maxmemory` | `2gb` |
| `maxmemory-policy` | `allkeys-lru` |
| Persistence | Off (`save ""`, `appendonly no`) |

**Docker Compose** mounts this config and starts Redis with:

```yaml
command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
```

**Apply / restart:**

```bash
docker compose up -d redis
```

**Verify:**

```bash
docker exec ai_support_redis redis-cli CONFIG GET maxmemory
docker exec ai_support_redis redis-cli CONFIG GET maxmemory-policy
```

Expected: `maxmemory` ≈ `2147483648`, `maxmemory-policy` = `allkeys-lru`.

---

## 3. Session TTL

| Setting | Value |
|---------|-------|
| Env var | `REDIS_SESSION_TTL_SECONDS` |
| Default | `86400` (24 hours) |
| Applied on | Every `SET` in session cache service |

---

## 4. Session key pattern

```
session:{user_id}:{session_id}
```

| Helper | Purpose |
|--------|---------|
| `session_key(user_id, session_id)` | Exact key for one session |
| `user_session_pattern(user_id)` | `session:{user_id}:*` for logout-all |

**Example:**

```
session:3fa85f64-5717-4562-b3fc-2c963f66afa6:7c9e6679-7425-40de-944b-e07fc1f90ae7
```

---

## 5. Session data structure

**Schema:** `backend/app/schemas/session.py`

```json
{
  "session_id": "uuid",
  "user_context": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "Jane Doe",
    "customer_type": "regular",
    "language": "en"
  },
  "last_activity": "2026-06-02T10:30:00Z",
  "permissions": ["chat:read", "chat:write", "ticket:create"]
}
```

| Field | Description |
|-------|-------------|
| `user_context` | Cached profile for authorization / personalization |
| `last_activity` | Updated on `touch()` |
| `permissions` | Scoped capabilities for this session |

---

## 6. Service API

**File:** `backend/app/services/session_cache.py`

| Method | Description |
|--------|-------------|
| `create(user_context, permissions?)` | Store new session with TTL |
| `get(user_id, session_id)` | Load session |
| `touch(user_id, session_id)` | Refresh activity + TTL |
| `update_permissions(...)` | Update permission list |
| `delete(user_id, session_id)` | Remove one session |
| `delete_all_for_user(user_id)` | Logout all devices |

**Usage example:**

```python
from uuid import UUID
from app.schemas.session import UserContext
from app.services.session_cache import SessionCacheService

service = SessionCacheService()
ctx = UserContext(
    user_id=UUID("..."),
    email="user@example.com",
    name="Jane Doe",
)
session = await service.create(ctx, permissions=["chat:read", "chat:write"])
```

---

## 7. Application wiring

| Component | Path |
|-----------|------|
| Redis client | `backend/app/core/redis.py` |
| Settings | `backend/app/core/config.py` |
| Session service | `backend/app/services/session_cache.py` |

---

## 8. Acceptance checklist

| Requirement | Done |
|-------------|------|
| maxmemory 2GB | ✅ |
| LRU eviction policy | ✅ |
| Session TTL 24h | ✅ |
| Key pattern `session:{user_id}:{session_id}` | ✅ |
| user_context + last_activity + permissions | ✅ |
