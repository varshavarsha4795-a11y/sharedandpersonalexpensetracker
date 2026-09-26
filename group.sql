-- SQLite
DROP TABLE IF EXISTS group_expense;

CREATE TABLE group_expense (
    group_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    expense_name TEXT NOT NULL,
    category TEXT NOT NULL,
    paid_by TEXT NOT NULL,
    amount REAL NOT NULL,
    members INTEGER NOT NULL,
    date TEXT NOT NULL
);