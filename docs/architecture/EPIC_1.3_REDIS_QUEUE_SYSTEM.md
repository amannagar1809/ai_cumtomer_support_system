# Epic 1.3 — Redis Queue System

**User Story 1.3.1** (queue system) · AI Customer Support System

---

## 1. Scope

| Task | Status |
|------|--------|
| Redis Streams message queues | ✅ |
| `escalation_queue`, `ticket_creation_queue`, `analytics_queue` | ✅ |
| Consumer groups with ACK tracking | ✅ |
| Dead-letter queue for failed messages | ✅ |
| Retry: 3 attempts, exponential backoff | ✅ |

---

## 2. Architecture

**Redis DB:** 2 (`REDIS_QUEUE_URL`)  
**Transport:** Redis Streams with consumer groups

```
Producer ──XADD──► escalation_queue ──XREADGROUP──► Worker ──XACK──► done
                         │                              │
                         │                         failure (×3)
                         │                              ▼
                         └────────────────────── dead_letter_queue
```

---

## 3. Queues

| Stream | Consumer group | Purpose |
|--------|----------------|---------|
| `escalation_queue` | `escalation_queue_workers` | Human-agent escalation requests |
| `ticket_creation_queue` | `ticket_creation_queue_workers` | Async ticket creation |
| `analytics_queue` | `analytics_queue_workers` | Analytics event ingestion |
| `dead_letter_queue` | `dead_letter_queue_workers` | Permanently failed messages |

Streams and groups are created on app startup (`MessageQueueService.ensure_streams()`).

---

## 4. Message envelope

Each stream entry stores flat string fields:

| Field | Description |
|-------|-------------|
| `event_type` | e.g. `escalation.requested`, `ticket.create`, `chat.message` |
| `payload` | JSON-encoded event body |
| `correlation_id` | Optional trace ID |
| `created_at` | ISO-8601 timestamp |
| `attempt` | Retry counter (starts at `0`) |
| `not_before` | Unix timestamp — message skipped until this time (backoff) |
| `last_error` | Last failure reason (on retry) |

**DLQ-only fields:** `source_stream`, `original_message_id`, `final_attempt`, `failed_at`

---

## 5. Consumer groups & acknowledgment

| Operation | Redis command | When |
|-----------|---------------|------|
| Read | `XREADGROUP` | Worker polls `>` (new messages) |
| Acknowledge | `XACK` | Handler succeeds |
| Pending count | `XPENDING` | Monitor unacked messages |

**Consumer naming:** `{service}-{hostname}` or `{service}-worker-{n}`

```python
messages = await queue.read_group(
    QueueName.analytics,
    consumer_name="analytics-worker-1",
)
for msg in messages:
    await process(msg)
    await queue.ack(QueueName.analytics, msg.message_id)
```

Or use `process_batch()` for automatic ACK / retry / DLQ handling.

---

## 6. Retry policy

| Setting | Default | Env var |
|---------|---------|---------|
| Max attempts | 3 | `QUEUE_MAX_RETRY_ATTEMPTS` |
| Base backoff | 1s | `QUEUE_RETRY_BASE_SECONDS` |
| Backoff formula | `base × 2^(attempt−1)` | — |

| Attempt | Delay before retry |
|---------|-------------------|
| 1 | 1s |
| 2 | 2s |
| 3 | → dead-letter queue |

On failure:
1. `XACK` original message (remove from pending)
2. Re-`XADD` with incremented `attempt` and `not_before` delay  
   **or** after 3 failures → `XADD` to `dead_letter_queue`

---

## 7. Dead-letter queue

Failed messages land in `dead_letter_queue` with:

```json
{
  "source_stream": "ticket_creation_queue",
  "original_message_id": "1717339200000-0",
  "final_attempt": 3,
  "failed_at": "2026-06-02T12:00:00Z",
  "last_error": "connection refused",
  "event_type": "ticket.create",
  "payload": { "...": "..." }
}
```

Inspect via Redis CLI:

```bash
docker exec ai_support_redis redis-cli -n 2 XRANGE dead_letter_queue - +
```

---

## 8. Configuration

| Env var | Default |
|---------|---------|
| `REDIS_QUEUE_URL` | `redis://localhost:6379/2` |
| `QUEUE_MAX_RETRY_ATTEMPTS` | `3` |
| `QUEUE_RETRY_BASE_SECONDS` | `1` |
| `QUEUE_CONSUMER_BLOCK_MS` | `5000` |

---

## 9. Usage examples

### Publish

```python
from app.services.message_queue import MessageQueueService
from app.schemas.queue import EscalationEvent, TicketCreationEvent, AnalyticsEvent

queue = MessageQueueService()

await queue.publish_escalation(EscalationEvent(
    conversation_id="...",
    user_id="...",
    reason="low_confidence",
))

await queue.publish_ticket_creation(TicketCreationEvent(
    conversation_id="...",
    user_id="...",
    category="billing",
    summary="Refund request",
))

await queue.publish_analytics(AnalyticsEvent(
    event_type="chat.message",
    conversation_id="...",
    properties={"channel": "web"},
))
```

### Consume

```python
async def handle_analytics(msg: QueueMessage) -> None:
    ...

await queue.process_batch(
    QueueName.analytics,
    consumer_name="analytics-worker-1",
    handler=handle_analytics,
)
```

---

## 10. Implementation map

| Component | Path |
|-----------|------|
| Queue service | `app/services/message_queue.py` |
| Schemas | `app/schemas/queue.py` |
| Redis client (DB 2) | `app/core/redis.py` → `get_queue_redis_client()` |
| Startup init | `app/main.py` lifespan |

---

## 11. Acceptance checklist

| Requirement | Done |
|-------------|------|
| Redis Streams | ✅ |
| `escalation_queue` | ✅ |
| `ticket_creation_queue` | ✅ |
| `analytics_queue` | ✅ |
| Consumer groups + ACK | ✅ |
| `dead_letter_queue` | ✅ |
| 3 attempts, exponential backoff | ✅ |
