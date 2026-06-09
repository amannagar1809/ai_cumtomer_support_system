# User Stories

## Epic 1.1: System Architecture Design

### User Story 1.1.1

**As a** System Architect  
**I want to** define all system components and their interactions  
**So that** the development team has a clear blueprint to follow.

#### Detailed tasks

- [x] Create component specification document listing all 8 core services
- [x] Design service communication matrix (sync vs async)
- [x] Define API contracts between each component (request/response schemas)
- [x] Create network topology diagram (placement, load balancers, firewalls)
- [x] Specify fallback mechanisms for each service failure scenario
- [x] Document scalability requirements (concurrent users, messages per second)
- [x] Define data retention policies per service

#### Deliverable

See [architecture/EPIC_1.1_SYSTEM_ARCHITECTURE.md](./architecture/EPIC_1.1_SYSTEM_ARCHITECTURE.md)

---

### User Story 1.1.2

**As a** Developer  
**I want** a complete data flow diagram  
**So that** I understand how information travels through the system.

#### Detailed tasks

- [x] Map end-to-end data flow from customer message to response delivery
- [x] Identify all data transformation points in the flow
- [x] Document data validation checkpoints
- [x] Specify error handling paths for each data flow branch
- [x] Create separate diagrams for: happy path, error scenarios, and escalation flows

#### Deliverable

See [architecture/EPIC_1.1_DATA_FLOW.md](./architecture/EPIC_1.1_DATA_FLOW.md)

---

## Epic 1.2: Database Design

### User Story 1.2.1 (in progress)

**As a** Backend Developer  
**I want** a complete PostgreSQL schema  
**So that** I can implement the data storage layer correctly.

#### Users table ΓÇö done

- [x] Fields, indexes, email/phone constraints

#### Conversations table ΓÇö done

- [x] Fields: id, user_id, channel, status, started_at, ended_at
- [x] Composite index on `(user_id, status)`
- [x] FK to users with `ON DELETE CASCADE`

#### Messages table ΓÇö done

- [x] Fields: id, conversation_id, sender_type, message, language, sentiment, timestamp
- [x] Full-text search GIN index on `message`
- [x] Monthly RANGE partition strategy + helper functions
- [x] 90-day archiving policy (`messages_archive` + `archive_messages_older_than`)

#### Tickets table ΓÇö done

- [x] Fields: id, conversation_id, priority, category, status, assigned_to, created_at, resolved_at
- [x] Indexes on priority, status, assigned_to
- [x] Automatic status transition rules (trigger + CHECK)

#### Deliverable

- [architecture/EPIC_1.2_DATABASE_SCHEMA.md](./architecture/EPIC_1.2_DATABASE_SCHEMA.md)
- Migrations: `20260602_0001_*` ΓÇª `20260602_0004_*`

---

### User Story 1.2.2

**As a** DBA  
**I want** database migrations and a backup strategy  
**So that** schema changes are trackable and data is secure.

#### Tasks

- [x] Alembic migration tool configured
- [x] Initial migration chain (all tables via `upgrade head`)
- [x] Rollback scripts per migration (Alembic + SQL)
- [x] Daily backup schedule + 35-day retention
- [x] Point-in-time recovery (WAL archiving + runbook)
- [x] Read replica for analytics queries

#### Deliverable

- [architecture/EPIC_1.2_MIGRATIONS_AND_BACKUP.md](./architecture/EPIC_1.2_MIGRATIONS_AND_BACKUP.md)
- Scripts: `backend/scripts/db/`
- Docker: `postgres-replica` and `postgres-backup` profiles

---

## Epic 1.3: Redis Setup

### User Story 1.3.1

**As a** DevOps Engineer  
**I want** Redis configured for multiple purposes  
**So that** the system has fast caching and queuing.

#### Session cache tasks

- [x] Redis maxmemory 2GB + LRU eviction policy
- [x] Session TTL 24 hours
- [x] Key pattern `session:{user_id}:{session_id}`
- [x] Session data structure (user context, last activity, permissions)

#### Chat memory tasks

- [x] Redis `db=1` for chat memory
- [x] Memory TTL 30 minutes
- [x] Key pattern `chat_memory:{conversation_id}:messages`
- [x] Sliding window expiration (TTL reset on each message)

#### User context tasks

- [x] Redis HASH `user_context:{user_id}`
- [x] Store preferred_language, last_conversation_id, sentiment_trend, active_ticket_ids
- [x] TTL 7 days for returning users
- [x] Context preload on conversation start

#### Rate limiting tasks

- [x] Token bucket algorithm
- [x] 10 messages/min per user, 1000 requests/min per IP
- [x] Key patterns `rate_limit:{user_id}:messages`, `rate_limit:{ip}:requests`
- [x] Custom 429 responses with Retry-After

#### Queue system tasks

- [x] Redis Streams for message queues
- [x] Queues: `escalation_queue`, `ticket_creation_queue`, `analytics_queue`
- [x] Consumer groups with acknowledgment tracking
- [x] Dead-letter queue `dead_letter_queue`
- [x] Retry policy: 3 attempts with exponential backoff

#### Deliverable

- [architecture/EPIC_1.3_REDIS_SESSION_CACHE.md](./architecture/EPIC_1.3_REDIS_SESSION_CACHE.md)
- [architecture/EPIC_1.3_REDIS_CHAT_MEMORY.md](./architecture/EPIC_1.3_REDIS_CHAT_MEMORY.md)
- [architecture/EPIC_1.3_REDIS_USER_CONTEXT.md](./architecture/EPIC_1.3_REDIS_USER_CONTEXT.md)
- [architecture/EPIC_1.3_REDIS_RATE_LIMITING.md](./architecture/EPIC_1.3_REDIS_RATE_LIMITING.md)
- [architecture/EPIC_1.3_REDIS_QUEUE_SYSTEM.md](./architecture/EPIC_1.3_REDIS_QUEUE_SYSTEM.md)
- Config: `backend/db/redis/redis.conf`
- Services: `session_cache.py`, `chat_memory.py`, `user_context_cache.py`, `rate_limiter.py`, `message_queue.py`

---

## Epic 2.1: Chat Interface

### User Story 2.1.1

**As a** Customer  
**I want to** start a new chat conversation  
**So that** I can get help immediately without logging in.

#### Tasks

- [x] Anonymous session initialization on page load
- [x] Temporary user ID in browser local storage
- [x] Chat widget with initial greeting message
- [x] Session ID associated with conversation record
- [x] Proactive chat trigger after 30 seconds of page inactivity

#### Deliverable

- API: `POST /api/v1/chat/sessions`, `GET /api/v1/chat/sessions/{session_id}`
- Service: `backend/app/services/chat_session.py`
- Frontend: `frontend/` (chat widget, localStorage, inactivity trigger)

### User Story 2.1.2

**As a** Customer  
**I want to** continue my previous chat  
**So that** I don't have to repeat my problem.

#### Tasks

- [x] Display "Continue Previous Conversation" button when returning user detected
- [x] Fetch last 10 messages from previous conversation on demand
- [x] Load conversation context into Redis before user types first message
- [x] Preserve conversation ID across sessions using browser storage
- [x] Show timestamp of last interaction ("Last active: 2 hours ago")

#### Deliverable

- API: `GET /api/v1/chat/returning-user`, `POST /api/v1/chat/conversations/{id}/continue`, `GET /api/v1/chat/conversations/{id}/messages`
- Service: `backend/app/services/message_store.py`
- Frontend: continue banner, relative time labels, `last_conversation_id` in localStorage
### User Story 2.1.3

**As a** Customer  
**I want to** upload files (screenshots, documents)  
**So that** I can better explain my issue.

#### Tasks

- [x] File upload button with drag-and-drop zone
- [x] Validate file types: images (jpg, png), PDF, text files
- [x] Enforce 10MB per file, 3 files per message
- [x] Chunked upload with progress indicator
- [x] Secure S3/GCS pre-signed URLs (local signed URLs for dev)
- [x] Pass file URLs to LangGraph via analytics queue (OCR flag)
- [x] Thumbnail previews of uploaded files

#### Deliverable

- API: `POST /api/v1/chat/uploads/init`, `PUT .../chunks/{n}`, `POST .../complete`
- Services: `file_upload.py`, `storage/`, `langgraph_attachments.py`
- Frontend: `file-upload.js`, drag-and-drop UI, previews
