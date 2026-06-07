-- Rollback: tickets table (revision 20260602_0004)
DROP TRIGGER IF EXISTS trg_tickets_status_rules ON tickets;
DROP FUNCTION IF EXISTS enforce_ticket_status_rules();
DROP TABLE IF EXISTS tickets CASCADE;
DROP TYPE IF EXISTS ticket_status;
DROP TYPE IF EXISTS ticket_priority;
