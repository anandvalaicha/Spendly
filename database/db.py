"""Database setup for Spendly — Step 1.

Provides three helpers used throughout the app:
    get_db()   — a SQLite connection with row_factory and foreign keys enabled
    init_db()  — creates all tables (CREATE TABLE IF NOT EXISTS)
    seed_db()  — inserts sample data for development

Run ``python -m database.db`` to create and seed a local development database.
"""

import sqlite3

from flask import g, has_app_context
from werkzeug.security import generate_password_hash

# The database file. Listed in .gitignore so it is never committed.
DATABASE = "expense_tracker.db"


# ------------------------------------------------------------------ #
# Connection                                                          #
# ------------------------------------------------------------------ #

def get_db():
    """Return a SQLite connection.

    Inside a Flask request the connection is cached on ``g`` and reused for the
    duration of that request. Outside an app context (e.g. running this module
    as a script) a fresh connection is opened each call.
    """
    if has_app_context():
        if "db" not in g:
            g.db = _connect()
        return g.db
    return _connect()


def _connect():
    """Open a new connection with row access by name and FK enforcement on."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_db(exception=None):
    """Close the request-scoped connection, if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Register teardown so the per-request connection is closed automatically."""
    app.teardown_appcontext(close_db)


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL UNIQUE,
    password   TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    description TEXT,
    date        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def init_db():
    """Create all tables if they do not already exist."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


# ------------------------------------------------------------------ #
# Seed data                                                           #
# ------------------------------------------------------------------ #

SEED_USERS = [
    # (name, email, plaintext password)
    ("Nitish Kumar", "nitish@example.com", "demo1234"),
    ("Anita Sharma", "anita@example.com", "demo1234"),
]

# Expenses keyed by the owner's email so seeding stays readable.
# (email, amount, category, description, date)
SEED_EXPENSES = [
    ("nitish@example.com", 45.00, "Groceries", "Weekly groceries", "2026-06-01"),
    ("nitish@example.com", 12.50, "Transport", "Metro card top-up", "2026-06-02"),
    ("nitish@example.com", 800.00, "Rent", "June rent", "2026-06-03"),
    ("nitish@example.com", 30.00, "Dining", "Dinner with friends", "2026-06-05"),
    ("anita@example.com", 60.00, "Groceries", "Supermarket run", "2026-06-04"),
    ("anita@example.com", 22.00, "Entertainment", "Movie tickets", "2026-06-06"),
]


def seed_db():
    """Insert sample users and expenses. Safe to run more than once."""
    db = get_db()

    for name, email, password in SEED_USERS:
        db.execute(
            "INSERT OR IGNORE INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
    db.commit()

    # Map seed emails to their user ids.
    rows = db.execute("SELECT id, email FROM users").fetchall()
    user_id_by_email = {row["email"]: row["id"] for row in rows}

    for email, amount, category, description, date in SEED_EXPENSES:
        user_id = user_id_by_email.get(email)
        if user_id is None:
            continue
        # Skip if this exact expense already exists, so re-runs don't duplicate.
        exists = db.execute(
            """SELECT 1 FROM expenses
               WHERE user_id = ? AND amount = ? AND category = ? AND date = ?""",
            (user_id, amount, category, date),
        ).fetchone()
        if exists:
            continue
        db.execute(
            """INSERT INTO expenses (user_id, amount, category, description, date)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, amount, category, description, date),
        )
    db.commit()


# ------------------------------------------------------------------ #
# Script entry point                                                  #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    init_db()
    seed_db()
    print(f"Initialized and seeded {DATABASE}")
