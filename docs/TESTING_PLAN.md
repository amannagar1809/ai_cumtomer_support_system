# Comprehensive Testing Plan - AI Customer Support System

## Overview
This document provides step-by-step testing instructions for all phases of the AI Customer Support System according to user story requirements.

## Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ installed
- Modern web browser (Chrome/Firefox/Edge)
- Postman or similar API testing tool (recommended)
- Terminal/Command Prompt access

---

## Phase 1: Environment Setup Testing

### Step 1.1: Start Docker Services
```bash
# Navigate to project root
cd c:\Users\aman\Desktop\Project\ai_customer_support_system

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

**Expected Result:**
- `postgres` container status: `Up (healthy)`
- `redis` container status: `Up (healthy)`

### Step 1.2: Check Service Logs
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Check Redis logs
docker-compose logs redis
```

**Expected Result:**
- No error messages in logs
- PostgreSQL shows "database system is ready to accept connections"
- Redis shows "Ready to accept connections"

---

## Phase 2: Database Testing (Epic 1.2)

### Step 2.1: Verify Database Connection
```bash
# Connect to PostgreSQL
docker exec -it ai_support_postgres psql -U postgres -d ai_support

# Run basic queries
SELECT version();
SELECT current_database();
\q
```

**Expected Result:**
- PostgreSQL 16.x version displayed
- Database name: `ai_support`

### Step 2.2: Verify Migrations Applied
```bash
cd backend
.venv\Scripts\activate

# Check migration status
alembic current

# View migration history
alembic history
```

**Expected Result:**
- Current revision shows latest migration
- All migrations show as applied in history

### Step 2.3: Verify Table Schema
```bash
docker exec -it ai_support_postgres psql -U postgres -d ai_support << 'EOF'
-- List all tables
\dt

-- Check users table structure
\d users

-- Check conversations table structure
\d conversations

-- Check messages table structure
\d messages

-- Check tickets table structure
\d tickets
EOF
```

**Expected Result:**
- Tables exist: `users`, `conversations`, `messages`, `tickets`
- Each table has correct columns and data types

### Step 2.4: Verify Indexes
```bash
docker exec -it ai_support_postgres psql -U postgres -d ai_support << 'EOF'
-- Check indexes on each table
SELECT indexname, tablename, indexdef 
FROM pg_indexes 
WHERE tablename IN ('users', 'conversations', 'messages', 'tickets')
ORDER BY tablename, indexname;
EOF
```

**Expected Result:**
- `users` table: indexes on email, phone
- `conversations` table: composite index on (user_id, status)
- `messages` table: GIN index on message column
- `tickets` table: indexes on priority, status, assigned_to

### Step 2.5: Verify Foreign Key Constraints
```bash
docker exec -it ai_support_postgres psql -U postgres -d ai_support << 'EOF
-- Check foreign key constraints
SELECT conname, conrelid::regclass AS table, confrelid::regclass AS references
FROM pg_constraint 
WHERE contype = 'f';
EOF
```

**Expected Result:**
- `conversations.user_id` references `users.id`
- `messages.conversation_id` references `conversations.id`
- `tickets.conversation_id` references `conversations.id`

---

## Phase 3: Redis Testing (Epic 1.3)

### Step 3.1: Verify Redis Connection
```bash
# Connect to Redis
docker exec -it ai_support_redis redis-cli

# Test connection
PING
INFO server
QUIT
```

**Expected Result:**
- `PONG` response
- Redis 7.x server information displayed

### Step 3.2: Test Session Cache (User Story 1.3.1)
```bash
docker exec -it ai_support_redis redis-cli << 'EOF'
-- Set a session with 24-hour TTL
SET session:user123:session456 '{"user_id": "123", "last_activity": "2024-01-01"}' EX 86400

-- Verify TTL
TTL session:user123:session456

-- Retrieve session
GET session:user123:session456

-- Clean up
DEL session:user123:session456
EOF
```

**Expected Result:**
- Session stored successfully
- TTL shows ~86400 seconds
- Session data retrievable

### Step 3.3: Test Chat Memory (User Story 1.3.1)
```bash
docker exec -it ai_support_redis redis-cli << 'EOF'
-- Switch to DB 1 for chat memory
SELECT 1

-- Add messages to chat memory
LPUSH chat_memory:conv1:messages '{"role": "user", "content": "Hello"}'
LPUSH chat_memory:conv1:messages '{"role": "assistant", "content": "Hi there"}'

-- Set 30-minute TTL
EXPIRE chat_memory:conv1:messages 1800

-- Retrieve messages
LRANGE chat_memory:conv1:messages 0 -1

-- Verify TTL
TTL chat_memory:conv1:messages

-- Clean up
DEL chat_memory:conv1:messages

-- Switch back to DB 0
SELECT 0
EOF
```

**Expected Result:**
- Messages stored in list
- TTL shows ~1800 seconds
- Messages retrievable in correct order

### Step 3.4: Test User Context (User Story 1.3.1)
```bash
docker exec -it ai_support_redis redis-cli << 'EOF'
-- Set user context fields
HSET user_context:user123 preferred_language "en"
HSET user_context:user123 last_conversation_id "conv1"
HSET user_context:user123 sentiment_trend "positive"
HSET user_context:user123 active_ticket_ids "ticket1,ticket2"

-- Set 7-day TTL
EXPIRE user_context:user123 604800

-- Retrieve all context
HGETALL user_context:user123

-- Verify TTL
TTL user_context:user123

-- Clean up
DEL user_context:user123
EOF
```

**Expected Result:**
- User context stored as hash
- All fields retrievable
- TTL shows ~604800 seconds

### Step 3.5: Test Rate Limiting (User Story 1.3.1)
```bash
docker exec -it ai_support_redis redis-cli << 'EOF'
-- Initialize rate limit counters
SET rate_limit:user123:messages 10 EX 60
SET rate_limit:192.168.1.1:requests 1000 EX 60

-- Simulate usage
DECR rate_limit:user123:messages
DECR rate_limit:192.168.1.1:requests

-- Check remaining
GET rate_limit:user123:messages
GET rate_limit:192.168.1.1:requests

-- Clean up
DEL rate_limit:user123:messages
DEL rate_limit:192.168.1.1:requests
EOF
```

**Expected Result:**
- Rate limit counters initialized
- Decrement operations work
- Remaining count accessible (should be 9 and 999)

---

## Phase 4: Backend API Testing

### Step 4.1: Start Backend Server
```bash
cd backend
.venv\Scripts\activate

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Result:**
- Server starts on `http://localhost:8000`
- No startup errors

### Step 4.2: Verify API Documentation
Open browser: `http://localhost:8000/docs`

**Expected Result:**
- Swagger UI displayed
- All API endpoints listed
- Interactive documentation available

### Step 4.3: Test Health Endpoint
```bash
# Using curl or Postman
curl http://localhost:8000/health
```

**Expected Result:**
- Status: `healthy`
- Database and Redis status shown

### Step 4.4: Test Chat Session Creation (User Story 2.1.1)
```bash
# Create new chat session
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "customer_external_id": null,
    "channel": "web",
    "metadata": {
      "locale": "en-US",
      "page_url": "http://localhost:8000"
    }
  }'
```

**Expected Result:**
- HTTP 201 Created
- Response contains `session_id` and `expires_at`

### Step 4.5: Test Send Message (User Story 2.1.1)
```bash
# Replace SESSION_ID from previous response
curl -X POST http://localhost:8000/api/v1/chat/sessions/SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello, I need help with my account",
    "attachments": []
  }'
```

**Expected Result:**
- HTTP 200 OK
- Response contains AI assistant message

### Step 4.6: Test File Upload (User Story 2.1.3)
```bash
# Initialize upload
curl -X POST http://localhost:8000/api/v1/chat/uploads/init \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.png",
    "file_size": 1024,
    "content_type": "image/png",
    "session_id": "SESSION_ID"
  }'
```

**Expected Result:**
- HTTP 200 OK
- Response contains upload ID and chunk URLs

### Step 4.7: Test Ticket Creation (User Story 2.1.4)
```bash
# Get user tickets
curl http://localhost:8000/api/v1/chat/tickets?user_id=USER_ID

# Create ticket via chat (escalation)
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "CONVERSATION_ID",
    "priority": "medium",
    "category": "technical",
    "subject": "Account login issue"
  }'
```

**Expected Result:**
- Tickets list returned
- New ticket created with ticket number

---

## Phase 5: Frontend Chat Interface Testing (Epic 2.1)

### Step 5.1: Open Frontend
Open browser: `file:///c:/Users/aman/Desktop/Project/ai_customer_support_system/frontend/index.html`

**Expected Result:**
- Chat widget loads
- Initial greeting message displayed

### Step 5.2: Test Anonymous Session (User Story 2.1.1)
**Scenario:**
1. Open page in incognito/private window
2. Observe chat widget behavior

**Expected Result:**
- Anonymous session initialized automatically
- Temporary user ID created in localStorage
- Chat widget shows greeting message

### Step 5.3: Test Send Message (User Story 2.1.1)
**Scenario:**
1. Type "Hello" in chat input
2. Click send button
3. Observe response

**Expected Result:**
- Message appears in chat window
- Typing indicator shows (3 dots animation)
- AI response received and displayed
- Session ID associated with conversation

### Step 5.4: Test Continue Previous Conversation (User Story 2.1.2)
**Scenario:**
1. Complete a chat session
2. Close browser tab
3. Reopen page in same browser
4. Check for "Continue Previous Conversation" option

**Expected Result:**
- "Continue Previous Conversation" button appears
- Clicking it loads last 10 messages
- Conversation context preserved

### Step 5.5: Test File Upload (User Story 2.1.3)
**Scenario:**
1. Click attachment icon in chat
2. Select a small image file (< 10MB)
3. Observe upload progress
4. Check thumbnail preview

**Expected Result:**
- File upload dialog opens
- Drag-and-drop zone functional
- File validation (type, size) works
- Progress indicator shows
- Thumbnail preview displayed

### Step 5.6: Test Ticket Status View (User Story 2.1.4)
**Scenario:**
1. Click "My Tickets" button in chat header
2. Observe ticket list
3. Click on a ticket to view details

**Expected Result:**
- Ticket panel overlay opens
- Shows ticket ID, status, priority, created date
- Real-time status updates work
- Option to reopen closed tickets available

### Step 5.7: Test Typing Indicator (User Story 2.1.5)
**Scenario:**
1. Send a message that requires AI processing
2. Observe typing indicator

**Expected Result:**
- Typing indicator (3 dots) appears
- Indicator disappears when response ready
- "Still working..." message appears after 5 seconds for long processes

### Step 5.8: Test WebSocket Connection
**Scenario:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by WS (WebSocket)
4. Send a message in chat

**Expected Result:**
- WebSocket connection established
- Events: `typing_start`, `typing_stop`, `message` visible
- Heartbeat mechanism working (ping/pong)

---

## Phase 6: Integration Testing

### Step 6.1: End-to-End Chat Flow
**Scenario:**
1. User opens chat widget
2. User sends: "I can't login to my account"
3. AI responds with troubleshooting steps
4. User escalates to human agent
5. Ticket created automatically

**Expected Result:**
- Complete flow works without errors
- Conversation saved to database
- Ticket created with correct priority
- Analytics events logged

### Step 6.2: Multi-Channel Testing
**Scenario:**
1. Test chat via web interface
2. Test via mobile (if mobile interface available)
3. Verify conversation continuity

**Expected Result:**
- Conversations sync across channels
- User context preserved
- Message history accessible

---

## Phase 7: Performance Testing

### Step 7.1: Database Query Performance
```bash
docker exec -it ai_support_postgres psql -U postgres -d ai_support << 'EOF'
-- Enable query timing
\timing on

-- Test message search with full-text index
SELECT * FROM messages 
WHERE message @@ to_tsquery('english', 'login')
LIMIT 10;

-- Test conversation lookup with index
SELECT * FROM conversations 
WHERE user_id = 1 AND status = 'active';

-- Disable timing
\timing off
EOF
```

**Expected Result:**
- Queries complete in < 100ms
- Index usage confirmed in EXPLAIN ANALYZE

### Step 7.2: Redis Performance
```bash
docker exec -it ai_support_redis redis-cli << 'EOF'
-- Test read/write performance
-- Run 1000 SET operations in a loop
-- Run 1000 GET operations in a loop
-- Measure time
EOF
```

**Expected Result:**
- Operations complete in < 1 second
- No significant latency

---

## Phase 8: Error Handling Testing

### Step 8.1: Test Invalid Input
**Scenario:**
1. Send empty message
2. Send message > 10000 characters
3. Upload invalid file type

**Expected Result:**
- Appropriate error messages displayed
- No server crashes
- Validation errors returned

### Step 8.2: Test Service Unavailability
**Scenario:**
1. Stop Redis container
2. Try to send message
3. Restart Redis
4. Try again

**Expected Result:**
- Graceful degradation
- Error message shown to user
- System recovers when service restored

### Step 8.3: Test Rate Limiting
**Scenario:**
1. Send messages rapidly (> 10 per minute)
2. Observe rate limit response

**Expected Result:**
- HTTP 429 status after limit
- Retry-After header present
- Rate limit error message displayed

---

## Phase 9: Security Testing

### Step 9.1: Test SQL Injection Protection
**Scenario:**
1. Send message with SQL injection attempt: `"'; DROP TABLE users; --"`
2. Verify database integrity

**Expected Result:**
- Message treated as plain text
- No SQL execution
- Database tables intact

### Step 9.2: Test XSS Protection
**Scenario:**
1. Send message with XSS: `<script>alert('XSS')</script>`
2. Check message display

**Expected Result:**
- Script not executed
- HTML escaped properly
- Safe display in chat

### Step 9.3: Test File Upload Security
**Scenario:**
1. Try uploading executable file (.exe)
2. Try uploading file > 10MB
3. Try uploading malicious file

**Expected Result:**
- File type validation works
- File size validation works
- Malicious files rejected

---

## Phase 10: Data Retention Testing

### Step 10.1: Test Message Archiving
```bash
-- Check archive function exists
docker exec -it ai_support_postgres psql -U postgres -d ai_support << 'EOF'
-- Test archive function (if implemented)
SELECT archive_messages_older_than(90);
EOF
```

**Expected Result:**
- Archive function executes
- Old messages moved to archive table

### Step 10.2: Test Redis TTL Expiration
**Scenario:**
1. Create session with short TTL (10 seconds)
2. Wait 11 seconds
3. Try to retrieve session

**Expected Result:**
- Session expired and removed
- Retrieval returns null

---

## Phase 11: Backup and Recovery Testing

### Step 11.1: Test Database Backup
```bash
# Start backup service
docker-compose --profile backup up -d

# Check backup logs
docker-compose logs postgres-backup
```

**Expected Result:**
- Backup service starts
- Backup files created in `backups/postgres/`

### Step 11.2: Test Point-in-Time Recovery
```bash
# Check WAL archive
docker exec -it ai_support_postgres ls -la //wal_archive
```

**Expected Result:**
- WAL files present
- Archive mechanism working

---

## Phase 12: Documentation Verification

### Step 12.1: Verify Architecture Documentation
- Open `docs/architecture/EPIC_1.1_SYSTEM_ARCHITECTURE.md`
- Verify all 8 services documented
- Verify API contracts match implementation

### Step 12.2: Verify Data Flow Documentation
- Open `docs/architecture/EPIC_1.1_DATA_FLOW.md`
- Verify data flow diagrams match actual flow
- Verify error handling paths documented

### Step 12.3: Verify Database Schema Documentation
- Open `docs/architecture/EPIC_1.2_DATABASE_SCHEMA.md`
- Compare with actual database schema
- Verify all tables, indexes, constraints documented

---

## Test Results Summary

Create a test results log:

```markdown
# Test Results Log

Date: [Current Date]
Tester: [Your Name]

## Environment
- OS: Windows
- Docker Version: [Version]
- Python Version: [Version]

## Phase Results
- [ ] Phase 1: Environment Setup - PASS/FAIL
- [ ] Phase 2: Database Testing - PASS/FAIL
- [ ] Phase 3: Redis Testing - PASS/FAIL
- [ ] Phase 4: Backend API Testing - PASS/FAIL
- [ ] Phase 5: Frontend Testing - PASS/FAIL
- [ ] Phase 6: Integration Testing - PASS/FAIL
- [ ] Phase 7: Performance Testing - PASS/FAIL
- [ ] Phase 8: Error Handling - PASS/FAIL
- [ ] Phase 9: Security Testing - PASS/FAIL
- [ ] Phase 10: Data Retention - PASS/FAIL
- [ ] Phase 11: Backup/Recovery - PASS/FAIL
- [ ] Phase 12: Documentation - PASS/FAIL

## Issues Found
1. [Issue description]
2. [Issue description]

## Notes
[Any additional observations]
```

---

## Cleanup

After testing complete:
```bash
# Stop all services
docker-compose down

# Remove volumes (optional - deletes all data)
docker-compose down -v
```
