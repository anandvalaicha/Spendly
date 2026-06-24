"""Tests for Step 8 — Edit Expense.

Covers the ``get_expense_by_id`` / ``update_expense`` query helpers and the
``GET``/``POST`` ``/expenses/<id>/edit`` route, per
``.claude/specs/08-edit-expense.md``.

Behaviour under test (spec, not implementation):
  - ``get_expense_by_id(expense_id, user_id)`` returns the row only when it
    belongs to ``user_id``; otherwise ``None`` (missing or other user's).
  - ``update_expense(expense_id, user_id, ...)`` updates in place scoped to both
    ``id`` and ``user_id``; returns rows affected; ``description=None`` is stored
    as SQL ``NULL``; editing another user's expense changes nothing (0 rows).
  - Both GET and POST require a logged-in session; otherwise redirect to
    ``/login``.
  - A missing expense, or one owned by another user, returns 404 for both GET and
    POST.
  - GET (authenticated, owned) renders a form pre-filled with current values and
    the correct category ``selected``.
  - POST (authenticated, valid) updates the row and redirects to ``/profile``.
  - POST validation failures re-render the form (200) with an error and do NOT
    change the row.
  - A blank description updates the row with ``description = NULL``.
"""

from database.queries import get_expense_by_id, insert_expense, update_expense

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


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
# get_expense_by_id — query helper                                   #
# ------------------------------------------------------------------ #

def test_get_expense_by_id_owned_returns_row(app, app_context, demo_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    row = get_expense_by_id(new_id, demo_id)
    assert row is not None
    assert row["id"] == new_id
    assert row["amount"] == 12.0
    assert row["category"] == "Food"


def test_get_expense_by_id_wrong_user_returns_none(app_context, demo_id, empty_user_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    assert get_expense_by_id(new_id, empty_user_id) is None


def test_get_expense_by_id_nonexistent_returns_none(app_context, demo_id):
    assert get_expense_by_id(999999, demo_id) is None


# ------------------------------------------------------------------ #
# update_expense — query helper                                      #
# ------------------------------------------------------------------ #

def test_update_expense_owned_updates_row(app, app_context, demo_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    affected = update_expense(new_id, demo_id, 99.0, "Bills", "2026-04-01", "Power")
    assert affected == 1

    from database.db import get_db
    row = get_db().execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    assert row["amount"] == 99.0
    assert row["category"] == "Bills"
    assert row["date"] == "2026-04-01"
    assert row["description"] == "Power"


def test_update_expense_wrong_user_changes_nothing(app, app_context, demo_id, empty_user_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    affected = update_expense(new_id, empty_user_id, 99.0, "Bills", "2026-04-01", "Power")
    assert affected == 0

    from database.db import get_db
    row = get_db().execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    # Original values are untouched.
    assert row["amount"] == 12.0
    assert row["category"] == "Food"
    assert row["description"] == "Lunch"


def test_update_expense_none_description_stored_as_null(app, app_context, demo_id):
    new_id = insert_expense(demo_id, 12.0, "Food", "2026-03-20", "Lunch")
    update_expense(new_id, demo_id, 12.0, "Food", "2026-03-20", None)

    from database.db import get_db
    row = get_db().execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    assert row["description"] is None


# ------------------------------------------------------------------ #
# GET /expenses/<id>/edit — auth + ownership                         #
# ------------------------------------------------------------------ #

def test_get_edit_unauthenticated_redirects_to_login(client, app, demo_id):
    expense_id = make_expense(app, demo_id)
    resp = client.get(f"/expenses/{expense_id}/edit")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_edit_owned_returns_prefilled_form(client, app, demo_id):
    expense_id = make_expense(
        app, demo_id, amount=42.5, category="Transport",
        date="2026-05-09", description="Train ticket",
    )
    login(client, demo_id)
    resp = client.get(f"/expenses/{expense_id}/edit")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<form" in body
    assert 'method="POST"' in body or 'method="post"' in body
    # Pre-filled current values.
    assert "42.5" in body
    assert "2026-05-09" in body
    assert "Train ticket" in body
    # The current category is pre-selected.
    assert 'value="Transport"' in body and "selected" in body


def test_get_edit_other_users_expense_returns_404(client, app, demo_id, empty_user_id):
    expense_id = make_expense(app, demo_id)
    login(client, empty_user_id, name="Newcomer")
    resp = client.get(f"/expenses/{expense_id}/edit")
    assert resp.status_code == 404


def test_get_edit_nonexistent_returns_404(client, demo_id):
    login(client, demo_id)
    resp = client.get("/expenses/999999/edit")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — auth + ownership                        #
# ------------------------------------------------------------------ #

def valid_payload(**overrides):
    payload = {
        "amount": "75.0",
        "category": "Bills",
        "date": "2026-06-01",
        "description": "Updated",
    }
    payload.update(overrides)
    return payload


def test_post_edit_unauthenticated_redirects_to_login(client, app, demo_id):
    expense_id = make_expense(app, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_edit_valid_data_redirects_and_updates(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload())
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    row = fetch_row(app, expense_id)
    assert row["amount"] == 75.0
    assert row["category"] == "Bills"
    assert row["date"] == "2026-06-01"
    assert row["description"] == "Updated"


def test_post_edit_other_users_expense_returns_404_and_no_change(client, app, demo_id, empty_user_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food", description="Lunch")
    login(client, empty_user_id, name="Newcomer")
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload())
    assert resp.status_code == 404

    row = fetch_row(app, expense_id)
    assert row["amount"] == 10.0
    assert row["category"] == "Food"
    assert row["description"] == "Lunch"


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — validation failures (no mutation)       #
# ------------------------------------------------------------------ #

def assert_unchanged(app, expense_id):
    row = fetch_row(app, expense_id)
    assert row["amount"] == 10.0
    assert row["category"] == "Food"


def test_post_edit_missing_amount_rerenders_with_error(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(amount=""))
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(w in body for w in ("required", "Required", "error", "Error"))
    assert_unchanged(app, expense_id)


def test_post_edit_zero_amount_rerenders_with_error(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(amount="0"))
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(w in body for w in ("greater", "zero", "error", "Error"))
    assert_unchanged(app, expense_id)


def test_post_edit_non_numeric_amount_rerenders_with_error(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(amount="abc"))
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(w in body for w in ("number", "error", "Error"))
    assert_unchanged(app, expense_id)


def test_post_edit_invalid_category_rerenders_with_error(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(category="Groceries"))
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(w in body for w in ("category", "Category", "error", "Error", "valid"))
    assert_unchanged(app, expense_id)


def test_post_edit_invalid_date_rerenders_with_error(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(date="not-a-date"))
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(w in body for w in ("date", "Date", "error", "Error", "valid"))
    assert_unchanged(app, expense_id)


# ------------------------------------------------------------------ #
# POST /expenses/<id>/edit — optional description                    #
# ------------------------------------------------------------------ #

def test_post_edit_blank_description_stores_null(client, app, demo_id):
    expense_id = make_expense(app, demo_id, amount=10.0, category="Food", description="Lunch")
    login(client, demo_id)
    resp = client.post(f"/expenses/{expense_id}/edit", data=valid_payload(description=""))
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    row = fetch_row(app, expense_id)
    assert row["description"] is None
