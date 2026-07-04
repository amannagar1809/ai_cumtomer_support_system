-- Rollback: conversations table (revision 20260602_0002)
DROP INDEX IF EXISTS ix_conversations_user_id_status;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TYPE IF EXISTS conversation_status;
DROP TYPE IF EXISTS conversation_channel;
