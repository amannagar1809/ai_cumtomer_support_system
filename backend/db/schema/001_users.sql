-- Epic 1.2 · User Story 1.2.1 — Users table only
-- Run via Alembic (preferred) or manually against ai_support database.

CREATE TYPE customer_type AS ENUM ('regular', 'premium', 'vip');

CREATE TABLE users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100)    NOT NULL,
    email           VARCHAR(255)    NOT NULL,
    phone           VARCHAR(20),
    language        VARCHAR(10)     NOT NULL DEFAULT 'en',
    customer_type   customer_type   NOT NULL DEFAULT 'regular',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email_format CHECK (
        email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    ),
    -- E.164: international phone (+{country}{number}, max 15 digits after +)
    CONSTRAINT ck_users_phone_e164 CHECK (
        phone IS NULL OR phone ~ '^\+[1-9][0-9]{1,14}$'
    )
);

CREATE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_phone ON users (phone);
CREATE INDEX ix_users_customer_type ON users (customer_type);

COMMENT ON TABLE users IS 'Customer accounts for AI support system';
COMMENT ON COLUMN users.phone IS 'E.164 format e.g. +14155552671, +919876543210';
