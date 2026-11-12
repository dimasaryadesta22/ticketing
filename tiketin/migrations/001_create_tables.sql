-- Migrasi awal Tiketin.
-- {PK}, {TS}, {NOW} diganti otomatis sesuai database (PostgreSQL / SQLite).

CREATE TABLE users (
    id {PK},
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at {TS} NOT NULL DEFAULT {NOW}
);

CREATE TABLE events (
    id {PK},
    name VARCHAR(150) NOT NULL,
    event_date DATE NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    quota INTEGER NOT NULL CHECK (quota > 0),
    sold INTEGER NOT NULL DEFAULT 0 CHECK (sold >= 0),
    created_at {TS} NOT NULL DEFAULT {NOW},
    CONSTRAINT events_sold_le_quota CHECK (sold <= quota)
);

CREATE TABLE tickets (
    id {PK},
    code VARCHAR(20) NOT NULL UNIQUE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CANCELLED')),
    purchased_at {TS} NOT NULL DEFAULT {NOW},
    cancelled_at {TS}
);

CREATE INDEX idx_tickets_event_user ON tickets (event_id, user_id, status);
CREATE INDEX idx_tickets_user ON tickets (user_id)
