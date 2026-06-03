-- Epic 1.2 · User Story 1.2.1 — Conversations table
-- Requires: 001_users.sql

CREATE TYPE conversation_channel AS ENUM (
    'web', 'whatsapp', 'email', 'telegram', 'mobile'
);

CREATE TYPE conversation_status AS ENUM (
    'active', 'resolved', 'escalated', 'closed'
);

CREATE TABLE conversations (
    id          UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID                    NOT NULL,
    channel     conversation_channel    NOT NULL,
    status      conversation_status     NOT NULL DEFAULT 'active',
    started_at  TIMESTAMP               NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at    TIMESTAMP,

    CONSTRAINT fk_conversations_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Active conversation lookups: WHERE user_id = ? AND status = 'active'
CREATE INDEX ix_conversations_user_id_status ON conversations (user_id, status);

COMMENT ON TABLE conversations IS 'Support chat sessions per user and channel';
COMMENT ON COLUMN conversations.ended_at IS 'NULL while conversation is open';
