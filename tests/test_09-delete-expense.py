"""Tests for Step 9 — Delete Expense.

Covers the ``delete_expense`` query helper and the POST-only
``/expenses/<id>/delete`` route, per ``.claude/specs/09-delete-expense.md``.

Behaviour under test (spec, not implementation):
  - ``delete_expense(expense_id, user_id)`` deletes in place scoped to both
    ``id`` and ``user_id``; returns rows affected; deleting another user's
    expense removes nothing (0 rows) and raises no error.
  - The route only accepts POST; a GET returns 405.
  - POST requires a logged-in session; otherwise redirect to ``/login`` and
    nothing is deleted.
  - A missing expense, or one owned by another user, returns 404 and leaves the
    row intact.
  - POST (authenticated, owned) deletes the row and redirects to ``/profile``.
"""

from database.queries import delete_expense, insert_expense


def login(client, user_id, name="Demo User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = name


def make_expense(app, user_id, amount=50.0, category="Food",
                 date="2026-03-20", description="Lunch"):
    """Insert one expense for ``user_id`` and return its new id."""
    with app.app_context():
        return insert_expense(user_id, amount, category, date, description)


def fetch_row(app, expense_id):
    with app.app_context():
        from database.db import get_db
        return get_db().execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()


# ------------------------------------------------------------------ #
# delete_expense — query helper                                      #
# ------------------------------------------------------------------ #

def test_delete_expense_owned_removes_row(app, app_context, demo_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    affected = delete_expense(new_id, demo_id)
    assert affected == 1

    from database.db import get_db
    row = get_db().execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    assert row is None


def test_delete_expense_wrong_user_changes_nothing(app, app_context, demo_id, empty_user_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    affected = delete_expense(new_id, empty_user_id)
    assert affected == 0

    from database.db import get_db
    row = get_db().execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    # The row still exists, untouched.
    assert row is not None
    assert row["amount"] == 12.0


def test_delete_expense_nonexistent_changes_nothing(app_context, demo_id):
    affected = delete_expense(999999, demo_id)
    assert affected == 0


# ------------------------------------------------------------------ #
# POST /expenses/<id>/delete — auth + ownership                      #
# ------------------------------------------------------------------ #

def test_post_delete_unauthenticated_redirects_to_login(client, app, demo_id):
    expense_id = make_expense(app, demo_id)
    resp = client.post(f"/expenses/{expense_id}/delete")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    # Nothing was deleted.
    assert fetch_row(app, expense_id) is not None


def test_post_delete_owned_redirects_and_removes(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/delete")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    assert fetch_row(app, expense_id) is None


def test_post_delete_other_users_expense_returns_404_and_no_change(client, app, demo_id, empty_user_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, empty_user_id, name="Newcomer")
    resp = client.post(f"/expenses/{expense_id}/delete")
    assert resp.status_code == 404
    # The owner's row is untouched.
    assert fetch_row(app, expense_id) is not None


def test_post_delete_nonexistent_returns_404(client, demo_id):
    login(client, demo_id)
    resp = client.post("/expenses/999999/delete")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# Method handling — route is POST-only                               #
# ------------------------------------------------------------------ #

def test_get_delete_returns_405(client, app, demo_id):
    expense_id = make_expense(app, demo_id)
    login(client, demo_id)
    resp = client.get(f"/expenses/{expense_id}/delete")
    assert resp.status_code == 405
    # A rejected GET deletes nothing.
    assert fetch_row(app, expense_id) is not None
