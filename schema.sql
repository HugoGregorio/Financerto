PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL COLLATE NOCASE,
    type        TEXT NOT NULL CHECK (type IN ('RECEITA', 'DESPESA')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (name, type),
    -- Needed so transactions can enforce that category and transaction types match.
    UNIQUE (id, type)
);

CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    description      TEXT NOT NULL CHECK (length(trim(description)) > 0),
    amount_cents     INTEGER NOT NULL CHECK (amount_cents > 0),
    type             TEXT NOT NULL CHECK (type IN ('RECEITA', 'DESPESA')),
    category_id      INTEGER NOT NULL,
    transaction_date TEXT NOT NULL,
    notes            TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (category_id, type)
        REFERENCES categories (id, type)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CHECK (length(transaction_date) = 10)
);

CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions (transaction_date);

CREATE INDEX IF NOT EXISTS idx_transactions_category
    ON transactions (category_id);

CREATE INDEX IF NOT EXISTS idx_transactions_type_date
    ON transactions (type, transaction_date);
