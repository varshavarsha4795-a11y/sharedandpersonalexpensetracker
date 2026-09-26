CREATE TABLE users (

    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT,
    created_at TEXT
);

CREATE TABLE income (
    income_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    source TEXT NOT NULL,
    date TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS expense (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    date TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS group_members (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,
    user_id INTEGER
);
CREATE TABLE IF NOT EXISTS group_expense (
    group_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,
    paid_by INTEGER,
    amount REAL NOT NULL,
    description TEXT,
    date TEXT
);
CREATE TABLE IF NOT EXISTS settlement (
    settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,
    payer_id INTEGER,
    receiver_id INTEGER,
    amount REAL,
    status TEXT DEFAULT 'Pending',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    currency TEXT,
    theme TEXT
);
