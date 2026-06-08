# Epic 1.3 — Redis Rate Limiting

**User Story 1.3.1** (rate limiting) · AI Customer Support System

---

## 1. Scope

| Task | Status |
|------|--------|
| Token bucket algorithm | ✅ |
| 10 messages/min per user | ✅ |
| 1000 requests/min per IP | ✅ |
| Key patterns | ✅ |
| Custom 429 responses | ✅ |

---

## 2. Algorithm — token bucket

Implemented in Redis with an atomic **Lua script** (HASH per key).

| Parameter | User messages | IP requests |
|-----------|---------------|-------------|
| Capacity | 10 tokens | 1000 tokens |
| Refill | 10 tokens / 60s | 1000 tokens / 60s |
| Cost per request | 1 token | 1 token |

**HASH fields:** `tokens`, `last_refill`  
**TTL:** 120s (key cleanup)

---

## 3. Key patterns

| Scope | Pattern | Example |
|-------|---------|---------|
| User messages | `rate_limit:{user_id}:messages` | `rate_limit:uuid:messages` |
| IP requests | `rate_limit:{ip}:requests` | `rate_limit:192.168.1.1:requests` |

**Redis DB:** 0

---

## 4. Limits (configurable)

| Env var | Default |
|---------|---------|
| `RATE_LIMIT_USER_MESSAGES_PER_MINUTE` | `10` |
| `RATE_LIMIT_IP_REQUESTS_PER_MINUTE` | `1000` |

---

## 5. Custom response — HTTP 429

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many messages. Please wait before sending again.",
    "request_id": "uuid",
    "details": {
      "limit": 10,
      "window": "1 minute",
      "retry_after_seconds": 6,
      "remaining": 0.0,
      "scope": "user_messages"
    }
  }
}
```

**Headers:** `Retry-After: <seconds>`, `X-Request-ID`

| `scope` | When |
|---------|------|
| `ip_requests` | IP middleware limit exceeded |
| `user_messages` | Per-user message limit exceeded |

---

## 6. Wiring

| Component | Path |
|-----------|------|
| Token bucket service | `app/services/rate_limiter.py` |
| IP middleware (global) | `app/main.py` → `IpRateLimitMiddleware` |
| User message dependency | `app/api/deps.py` → `enforce_user_message_rate_limit` |
| Exception handler | `app/core/rate_limit_handlers.py` |

### IP limit (automatic)

Applied to all routes except `/health`, `/health/ready`, `/docs`, `/openapi.json`, `/redoc`.

### User message limit (per endpoint)

Use on chat/message routes when implemented:

```python
from uuid import UUID
from fastapi import Depends
from app.api.deps import enforce_user_message_rate_limit

@router.post("/conversations/{id}/messages")
async def send_message(
    user_id: UUID,
    _: None = Depends(enforce_user_message_rate_limit),  # via wrapper
):
    ...
```

Or call directly:

```python
await enforce_user_message_rate_limit(user_id)
```

---

## 7. Verify

```bash
# Inspect bucket state
docker exec ai_support_redis redis-cli -n 0 HGETALL rate_limit:127.0.0.1:requests
```

Repeated rapid requests should return **429** with the custom JSON body.

---

## 8. Acceptance checklist

| Requirement | Done |
|-------------|------|
| Token bucket algorithm | ✅ |
| 10 msg/min per user | ✅ |
| 1000 req/min per IP | ✅ |
| `rate_limit:{user_id}:messages` | ✅ |
| `rate_limit:{ip}:requests` | ✅ |
| Custom rate-limit response | ✅ |
