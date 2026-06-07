-- Rollback: users table (revision 20260602_0001)
DROP INDEX IF EXISTS ix_users_customer_type;
DROP INDEX IF EXISTS ix_users_phone;
DROP INDEX IF EXISTS ix_users_email;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS customer_type;
