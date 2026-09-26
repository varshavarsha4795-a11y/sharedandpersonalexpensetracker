-- SQLite
DROP TABLE IF EXISTS settlement;

CREATE TABLE settlement (
    settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    member_name TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'Pending'
);