-- Epic 1.2 · User Story 1.2.1 — Tickets table
-- Requires: 002_conversations.sql

CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'resolved', 'closed');

CREATE TABLE tickets (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID            NOT NULL,
    priority        ticket_priority NOT NULL DEFAULT 'medium',
    category        VARCHAR(50)     NOT NULL,
    status          ticket_status   NOT NULL DEFAULT 'open',
    assigned_to     VARCHAR(100),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP,

    CONSTRAINT fk_tickets_conversation_id_conversations
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
    CONSTRAINT ck_tickets_resolved_at_consistency CHECK (
        (status IN ('open', 'in_progress') AND resolved_at IS NULL)
        OR (status IN ('resolved', 'closed') AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX ix_tickets_priority ON tickets (priority);
CREATE INDEX ix_tickets_status ON tickets (status);
CREATE INDEX ix_tickets_assigned_to ON tickets (assigned_to);

COMMENT ON TABLE tickets IS 'Support tickets escalated from conversations';
COMMENT ON COLUMN tickets.assigned_to IS 'Agent identifier or display name (max 100 chars)';

-- ---------------------------------------------------------------------------
-- Automatic status transition rules (BEFORE INSERT/UPDATE trigger)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_ticket_status_rules()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    transition_allowed BOOLEAN;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status IS DISTINCT FROM 'open'::ticket_status THEN
            RAISE EXCEPTION 'New tickets must start with status open (got %)', NEW.status;
        END IF;
        NEW.resolved_at := NULL;
        RETURN NEW;
    END IF;

    -- No status change: sync resolved_at if inconsistent
    IF OLD.status = NEW.status THEN
        IF NEW.status IN ('resolved', 'closed') AND NEW.resolved_at IS NULL THEN
            NEW.resolved_at := CURRENT_TIMESTAMP;
        ELSIF NEW.status IN ('open', 'in_progress') THEN
            NEW.resolved_at := NULL;
        END IF;
        RETURN NEW;
    END IF;

    transition_allowed := CASE
        WHEN OLD.status = 'open' AND NEW.status IN ('in_progress', 'closed') THEN TRUE
        WHEN OLD.status = 'in_progress' AND NEW.status IN ('open', 'resolved', 'closed') THEN TRUE
        WHEN OLD.status = 'resolved' AND NEW.status IN ('open', 'in_progress', 'closed') THEN TRUE
        WHEN OLD.status = 'closed' AND NEW.status IN ('open', 'in_progress') THEN TRUE
        ELSE FALSE
    END;

    IF NOT transition_allowed THEN
        RAISE EXCEPTION
            'Invalid ticket status transition: % -> %',
            OLD.status, NEW.status;
    END IF;

    IF NEW.status IN ('resolved', 'closed') THEN
        IF NEW.resolved_at IS NULL THEN
            NEW.resolved_at := CURRENT_TIMESTAMP;
        END IF;
    ELSE
        NEW.resolved_at := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_tickets_status_rules
    BEFORE INSERT OR UPDATE OF status, resolved_at ON tickets
    FOR EACH ROW
    EXECUTE FUNCTION enforce_ticket_status_rules();
