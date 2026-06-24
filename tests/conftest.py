"""Shared pytest fixtures for the Spendly test suite.

Each test runs against a fresh, isolated SQLite database seeded with the
development data, so tests never touch the real ``spendly.db``.
"""

import pytest

import database.db as dbmod
from app import app as flask_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The Flask app wired to a fresh, seeded temp database."""
    monkeypatch.setattr(dbmod, "DATABASE", str(tmp_path / "test.db"))
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        dbmod.init_db()
        dbmod.seed_db()
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Push an application context so query helpers can call get_db()."""
    with app.app_context():
        yield


@pytest.fixture
def demo_id(app):
    """The id of the seeded Demo User."""
    with app.app_context():
        row = dbmod.get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        return row["id"]


@pytest.fixture
def empty_user_id(app):
    """A user with no expenses."""
    with app.app_context():
        db = dbmod.get_db()
        db.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            ("Newcomer", "new@spendly.com", "x"),
        )
        db.commit()
        row = db.execute(
            "SELECT id FROM users WHERE email = ?", ("new@spendly.com",)
        ).fetchone()
        return row["id"]
