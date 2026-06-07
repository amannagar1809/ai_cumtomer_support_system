-- Rollback: messages table (revision 20260602_0003)
DROP FUNCTION IF EXISTS archive_messages_older_than(INT);
DROP FUNCTION IF EXISTS ensure_messages_partitions(INT);
DROP FUNCTION IF EXISTS create_messages_partition(INT, INT);
DROP TABLE IF EXISTS messages_archive CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TYPE IF EXISTS message_sender_type;
