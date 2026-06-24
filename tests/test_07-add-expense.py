"""Tests for Step 7 — Add Expense.

Covers the ``insert_expense`` query helper and the ``GET``/``POST``
``/expenses/add`` route, per ``.claude/specs/07-add-expense.md``.

Behaviour under test (spec, not implementation):
  - ``insert_expense(user_id, amount, category, date, description)`` inserts a
    row scoped to ``user_id``; ``description=None`` is stored as SQL ``NULL``.
  - Both GET and POST ``/expenses/add`` require a logged-in session; otherwise
    redirect to ``/login``.
  - GET (authenticated) renders a form with a POST method and a category
    ``<select>`` containing exactly the 7 fixed categories: Food, Transport,
    Bills, Health, Entertainment, Shopping, Other.
  - POST (authenticated, valid) inserts the expense and redirects to
    ``/profile``.
  - POST validation failures (missing/zero/negative/non-numeric amount,
    invalid category, missing/invalid date) re-render the form (200) with an
    error message and do NOT insert a row.
  - A missing/blank description is optional and stored as NULL; the request
    still succeeds.
  - Failed submissions redisplay the user's previously entered values.

The spec defines no future-date restriction, so none is tested here.
"""

from database.queries import insert_expense

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


# ------------------------------------------------------------------ #
# insert_expense — query helper                                      #
# ------------------------------------------------------------------ #

def test_insert_expense_valid_row_is_queryable(app_context, demo_id):
    """A valid insert creates a row that can be read back with the same values."""
    insert_expense(demo_id, 50.0, "Food", "2026-03-20", "Lunch")

    from database.db import get_db
    row = get_db().execute(
        "SELECT * FROM expenses WHERE user_id = ? AND description = ?",
        (demo_id, "Lunch"),
    ).fetchone()

    assert row is not None, "Expected the inserted expense to be queryable"
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"
    assert row["description"] == "Lunch"


def test_insert_expense_none_description_stored_as_null(app_context, demo_id):
    """description=None must be stored as SQL NULL, not the string 'None'."""
    new_id = insert_expense(demo_id, 12.5, "Transport", "2026-04-01", None)

    from database.db import get_db
    row = get_db().execute(
        "SELECT * FROM expenses WHERE id = ?", (new_id,)
    ).fetchone()

    assert row is not None
    assert row["description"] is None, "Expected NULL description, not a string"


# ------------------------------------------------------------------ #
# GET /expenses/add — auth guard                                     #
# ------------------------------------------------------------------ #

def test_get_add_expense_unauthenticated_redirects_to_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# GET /expenses/add — authenticated                                  #
# ------------------------------------------------------------------ #

def test_get_add_expense_authenticated_returns_200(client, demo_id):
    login(client, demo_id)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200


def test_get_add_expense_authenticated_contains_post_form(client, demo_id):
    login(client, demo_id)
    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)
    assert "<form" in body, "Expected a <form> element in the response"
    # The form tag (or one near the top) should declare a POST method.
    assert 'method="POST"' in body or 'method="post"' in body


def test_get_add_expense_authenticated_contains_all_fixed_categories(client, demo_id):
    login(client, demo_id)
    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)
    assert "<select" in body, "Expected a <select> element for category"
    for category in CATEGORIES:
        assert category in body, f"Expected category '{category}' in the form"


# ------------------------------------------------------------------ #
# POST /expenses/add — auth guard                                    #
# ------------------------------------------------------------------ #

def test_post_add_expense_unauthenticated_redirects_to_login(client):
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# POST /expenses/add — authenticated, valid data                     #
# ------------------------------------------------------------------ #

def test_post_add_expense_valid_data_redirects_to_profile(client, demo_id):
    login(client, demo_id)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_post_add_expense_valid_data_inserts_row_for_user(client, app, demo_id):
    login(client, demo_id)
    client.post(
        "/expenses/add",
        data={
            "amount": "50.0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
    )

    with app.app_context():
        from database.db import get_db
        row = get_db().execute(
            "SELECT * FROM expenses WHERE user_id = ? AND description = ?",
            (demo_id, "Lunch"),
        ).fetchone()

    assert row is not None, "Expected the new expense to exist in the database"
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"


# ------------------------------------------------------------------ #
# POST /expenses/add — validation failures                           #
# ------------------------------------------------------------------ #

def valid_payload(**overrides):
    payload = {
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20",
        "description": "Lunch",
    }
    payload.update(overrides)
    return payload


def count_expenses(app, user_id):
    with app.app_context():
        from database.db import get_db
        row = get_db().execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["c"]


def test_post_add_expense_missing_amount_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(amount=""))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<form" in body
    assert any(
        word in body for word in ("required", "Required", "error", "Error")
    ), "Expected an error message in the re-rendered form"
    assert count_expenses(app, demo_id) == before, "No row should be inserted on validation failure"


def test_post_add_expense_zero_amount_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(amount="0"))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("greater", "zero", "error", "Error")
    ), "Expected an error message about a non-positive amount"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_negative_amount_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(amount="-10"))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("greater", "zero", "positive", "error", "Error")
    ), "Expected an error message about a negative amount"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_non_numeric_amount_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(amount="abc"))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("number", "error", "Error")
    ), "Expected an error message about a non-numeric amount"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_missing_category_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(category=""))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("category", "Category", "error", "Error")
    ), "Expected an error message about category"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_invalid_category_rerenders_with_error(client, app, demo_id):
    """A category not in the fixed list (e.g. 'Groceries') must be rejected."""
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(category="Groceries"))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("category", "Category", "error", "Error", "valid")
    ), "Expected an error message about an invalid category"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_missing_date_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(date=""))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("date", "Date", "error", "Error")
    ), "Expected an error message about a missing date"
    assert count_expenses(app, demo_id) == before


def test_post_add_expense_invalid_date_rerenders_with_error(client, app, demo_id):
    login(client, demo_id)
    before = count_expenses(app, demo_id)

    resp = client.post("/expenses/add", data=valid_payload(date="not-a-date"))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert any(
        word in body for word in ("date", "Date", "error", "Error", "valid")
    ), "Expected an error message about an invalid date"
    assert count_expenses(app, demo_id) == before


# ------------------------------------------------------------------ #
# POST /expenses/add — optional description                          #
# ------------------------------------------------------------------ #

def test_post_add_expense_no_description_redirects_to_profile(client, demo_id):
    login(client, demo_id)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "20.0",
            "category": "Bills",
            "date": "2026-05-01",
        },
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_post_add_expense_no_description_inserts_row_with_null_description(client, app, demo_id):
    login(client, demo_id)
    client.post(
        "/expenses/add",
        data={
            "amount": "20.0",
            "category": "Bills",
            "date": "2026-05-01",
        },
    )

    with app.app_context():
        from database.db import get_db
        row = get_db().execute(
            "SELECT * FROM expenses WHERE user_id = ? AND amount = ? AND date = ?",
            (demo_id, 20.0, "2026-05-01"),
        ).fetchone()

    assert row is not None, "Expected the new expense row to exist"
    assert row["description"] is None, "Expected NULL description when none was submitted"


# ------------------------------------------------------------------ #
# POST /expenses/add — form repopulation on failure                  #
# ------------------------------------------------------------------ #

def test_post_add_expense_failed_submission_preserves_entered_values(client, demo_id):
    """A rejected submission should redisplay the values the user typed."""
    login(client, demo_id)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "abc",
            "category": "Food",
            "date": "2026-07-01",
            "description": "Coffee with friends",
        },
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Food" in body
    assert "2026-07-01" in body
    assert "Coffee with friends" in body
