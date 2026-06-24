"""Tests for Step 5 — backend connection of the profile page.

Covers the pure query helpers in ``database.queries`` and the ``/profile``
route. The seed data is a single Demo User with eight expenses across seven
categories totalling 346.24, with "Bills" as the top category.
"""

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

TXN_KEYS = {"date", "description", "category", "amount"}


# ------------------------------------------------------------------ #
# get_user_by_id                                                      #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid(app_context, demo_id):
    user = get_user_by_id(demo_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["member_since"]  # non-empty, formatted "Month YYYY"


def test_get_user_by_id_missing(app_context):
    assert get_user_by_id(999999) is None


# ------------------------------------------------------------------ #
# get_summary_stats                                                   #
# ------------------------------------------------------------------ #

def test_get_summary_stats_with_expenses(app_context, demo_id):
    stats = get_summary_stats(demo_id)
    assert round(stats["total_spent"], 2) == 346.24
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(app_context, empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


# ------------------------------------------------------------------ #
# get_recent_transactions                                            #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_with_expenses(app_context, demo_id):
    txns = get_recent_transactions(demo_id)
    assert len(txns) == 8
    for tx in txns:
        assert TXN_KEYS <= set(tx)
    # Newest-first ordering by date.
    dates = [tx["date"] for tx in txns]
    assert dates == sorted(dates, reverse=True)
    assert txns[0]["date"] == "2026-06-20"


def test_get_recent_transactions_respects_limit(app_context, demo_id):
    assert len(get_recent_transactions(demo_id, limit=3)) == 3


def test_get_recent_transactions_no_expenses(app_context, empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


# ------------------------------------------------------------------ #
# get_category_breakdown                                             #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_with_expenses(app_context, demo_id):
    cats = get_category_breakdown(demo_id)
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert cats[0]["name"] == "Bills"
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_no_expenses(app_context, empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


# ------------------------------------------------------------------ #
# GET /profile route                                                 #
# ------------------------------------------------------------------ #

def test_profile_unauthenticated_redirects(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated_renders_real_data(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "346.24" in body
    assert "Bills" in body
    # All seven categories appear.
    for category in (
        "Bills", "Groceries", "Dining", "Shopping",
        "Health", "Transport", "Entertainment",
    ):
        assert category in body
    # Newest transaction (Jun 20) renders before the oldest (Jun 02).
    assert body.index("Electricity bill") < body.index("New headphones")


def test_profile_new_user_empty_state(client, empty_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = empty_user_id
        sess["user_name"] = "Newcomer"

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "₹0.00" in body
    assert "No transactions yet." in body
