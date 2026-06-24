"""Tests for Step 6 — date filter for the profile page.

Covers the optional ``date_from``/``date_to`` keyword args on the three query
helpers in ``database.queries`` and the date-range filtering behaviour of the
``GET /profile`` route. The seed data is a single Demo User with eight
expenses across seven categories totalling 346.24, dated 2026-06-02 through
2026-06-20, with "Bills" as the top category.

Per the spec, a filter only applies when BOTH ``date_from`` and ``date_to``
are present and well-formed ISO dates with ``date_from <= date_to``. Anything
else (absent param, malformed date, reversed range) falls back to the
unfiltered "All Time" view without raising, and a reversed range additionally
surfaces the message "Start date must be before end date." on the page.
"""

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

TXN_KEYS = {"date", "description", "category", "amount"}

# Inclusive range covering exactly three of the seed expenses:
#   Electricity bill  89.99  2026-06-20  (Bills)
#   Dinner out         52.40  2026-06-15  (Dining)
#   Weekly groceries   45.00  2026-06-18  (Groceries)
# Total: 187.39. "Cab fares" (2026-06-12, Transport) must NOT appear.
RANGE_FROM = "2026-06-15"
RANGE_TO = "2026-06-20"
RANGE_TOTAL = 187.39
RANGE_COUNT = 3

# A range with no seed expenses in it at all.
EMPTY_FROM = "2020-01-01"
EMPTY_TO = "2020-01-31"


# ------------------------------------------------------------------ #
# get_summary_stats — date filtering                                  #
# ------------------------------------------------------------------ #

def test_get_summary_stats_unfiltered_matches_step5_baseline(app_context, demo_id):
    """No date args behaves exactly like the Step 5 unfiltered call."""
    stats = get_summary_stats(demo_id)
    assert round(stats["total_spent"], 2) == 346.24
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_filtered_range(app_context, demo_id):
    stats = get_summary_stats(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    assert round(stats["total_spent"], 2) == RANGE_TOTAL
    assert stats["transaction_count"] == RANGE_COUNT


def test_get_summary_stats_filtered_top_category_within_range(app_context, demo_id):
    # Within 06-15..06-20: Bills 89.99, Dining 52.40, Groceries 45.00 -> Bills wins.
    stats = get_summary_stats(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_empty_range_returns_zeros(app_context, demo_id):
    stats = get_summary_stats(demo_id, date_from=EMPTY_FROM, date_to=EMPTY_TO)
    assert stats == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_summary_stats_only_one_bound_given_is_unfiltered(app_context, demo_id):
    """A single bound (the other missing) must not filter at all."""
    stats_from_only = get_summary_stats(demo_id, date_from=RANGE_FROM)
    stats_to_only = get_summary_stats(demo_id, date_to=RANGE_TO)
    baseline = get_summary_stats(demo_id)
    assert stats_from_only == baseline
    assert stats_to_only == baseline


# ------------------------------------------------------------------ #
# get_recent_transactions — date filtering                            #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_unfiltered_matches_step5_baseline(app_context, demo_id):
    txns = get_recent_transactions(demo_id)
    assert len(txns) == 8
    for tx in txns:
        assert TXN_KEYS <= set(tx)


def test_get_recent_transactions_filtered_range_contains_expected_rows(app_context, demo_id):
    txns = get_recent_transactions(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    assert len(txns) == RANGE_COUNT

    descriptions = {tx["description"] for tx in txns}
    assert descriptions == {"Electricity bill", "Dinner out", "Weekly groceries"}

    total = round(sum(tx["amount"] for tx in txns), 2)
    assert total == RANGE_TOTAL


def test_get_recent_transactions_filtered_excludes_out_of_range_expense(app_context, demo_id):
    txns = get_recent_transactions(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    descriptions = {tx["description"] for tx in txns}
    assert "Cab fares" not in descriptions, "Cab fares (2026-06-12) is outside the filtered range"


def test_get_recent_transactions_filtered_still_newest_first(app_context, demo_id):
    txns = get_recent_transactions(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    dates = [tx["date"] for tx in txns]
    assert dates == sorted(dates, reverse=True)


def test_get_recent_transactions_filtered_respects_limit(app_context, demo_id):
    txns = get_recent_transactions(demo_id, limit=2, date_from=RANGE_FROM, date_to=RANGE_TO)
    assert len(txns) == 2


def test_get_recent_transactions_empty_range_returns_empty_list(app_context, demo_id):
    assert get_recent_transactions(demo_id, date_from=EMPTY_FROM, date_to=EMPTY_TO) == []


# ------------------------------------------------------------------ #
# get_category_breakdown — date filtering                             #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_unfiltered_matches_step5_baseline(app_context, demo_id):
    cats = get_category_breakdown(demo_id)
    assert len(cats) == 7
    assert cats[0]["name"] == "Bills"


def test_get_category_breakdown_filtered_range(app_context, demo_id):
    cats = get_category_breakdown(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    names = {c["name"] for c in cats}
    assert names == {"Bills", "Dining", "Groceries"}
    assert "Transport" not in names, "Cab fares' category should not appear in the filtered breakdown"


def test_get_category_breakdown_filtered_percentages_sum_to_100(app_context, demo_id):
    cats = get_category_breakdown(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    assert sum(c["pct"] for c in cats) == 100
    assert all(isinstance(c["pct"], int) for c in cats)


def test_get_category_breakdown_filtered_ordered_by_amount_desc(app_context, demo_id):
    cats = get_category_breakdown(demo_id, date_from=RANGE_FROM, date_to=RANGE_TO)
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert cats[0]["name"] == "Bills"


def test_get_category_breakdown_empty_range_returns_empty_list(app_context, demo_id):
    assert get_category_breakdown(demo_id, date_from=EMPTY_FROM, date_to=EMPTY_TO) == []


# ------------------------------------------------------------------ #
# GET /profile — auth guard                                           #
# ------------------------------------------------------------------ #

def test_profile_unauthenticated_redirects_even_with_filter_params(client):
    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# GET /profile — unfiltered baseline                                  #
# ------------------------------------------------------------------ #

def test_profile_no_query_params_shows_all_time_unfiltered_data(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "346.24" in body
    assert "Bills" in body
    # Unfiltered view includes every seed expense, including ones outside
    # the custom range used elsewhere in this file.
    assert "Cab fares" in body
    assert "New headphones" in body
    assert "$" in body


# ------------------------------------------------------------------ #
# GET /profile — valid custom range                                   #
# ------------------------------------------------------------------ #

def test_profile_valid_range_filters_all_three_sections(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Summary stats reflect the filtered total/count.
    assert "187.39" in body
    assert '<span class="stat-value">3</span>' in body, "Filtered transaction count should render as 3"

    # Recent transactions: in-range items present, out-of-range item absent.
    assert "Electricity bill" in body
    assert "Dinner out" in body
    assert "Weekly groceries" in body
    assert "Cab fares" not in body, "Out-of-range expense must not appear in filtered view"
    assert "New headphones" not in body, "Out-of-range expense must not appear in filtered view"


def test_profile_valid_range_prepopulates_date_inputs(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    body = resp.get_data(as_text=True)
    assert f'value="{RANGE_FROM}"' in body
    assert f'value="{RANGE_TO}"' in body


def test_profile_valid_range_no_error_message_shown(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    body = resp.get_data(as_text=True)
    assert "Start date must be before end date." not in body


# ------------------------------------------------------------------ #
# GET /profile — reversed range                                       #
# ------------------------------------------------------------------ #

def test_profile_reversed_range_shows_error_and_falls_back_unfiltered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_TO}&date_to={RANGE_FROM}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Start date must be before end date." in body
    # Falls back to the full unfiltered totals.
    assert "346.24" in body


# ------------------------------------------------------------------ #
# GET /profile — malformed / partial params                           #
# ------------------------------------------------------------------ #

def test_profile_malformed_date_from_does_not_crash_and_falls_back(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from=not-a-date&date_to={RANGE_TO}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "346.24" in body


def test_profile_malformed_date_to_does_not_crash_and_falls_back(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to=banana")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "346.24" in body


def test_profile_only_date_from_present_falls_back_unfiltered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "346.24" in body


def test_profile_only_date_to_present_falls_back_unfiltered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_to={RANGE_TO}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "346.24" in body


# ------------------------------------------------------------------ #
# GET /profile — empty result range                                   #
# ------------------------------------------------------------------ #

def test_profile_empty_range_shows_zero_total_and_no_transactions(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={EMPTY_FROM}&date_to={EMPTY_TO}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "$0.00" in body
    assert "No transactions yet." in body
    assert "Start date must be before end date." not in body


def test_profile_empty_range_category_breakdown_is_empty(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={EMPTY_FROM}&date_to={EMPTY_TO}")
    body = resp.get_data(as_text=True)
    assert "No spending to break down yet." in body


# ------------------------------------------------------------------ #
# GET /profile — quick-select presets                                 #
# ------------------------------------------------------------------ #

def test_profile_all_time_preset_link_has_no_query_params(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert 'href="/profile"' in body, "All Time preset must link to a clean /profile URL"


def test_profile_preset_buttons_all_present(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
        assert label in body


def test_profile_all_time_is_active_when_unfiltered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    # The "All Time" link should carry the active-state class when no filter applies.
    all_time_idx = body.find(">All Time<")
    assert all_time_idx != -1
    preceding = body[:all_time_idx]
    anchor_start = preceding.rfind("<a ")
    anchor_tag = body[anchor_start:all_time_idx]
    assert "is-active" in anchor_tag


# ------------------------------------------------------------------ #
# GET /profile — currency symbol always present                       #
# ------------------------------------------------------------------ #

def test_profile_currency_symbol_present_unfiltered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert "$" in body


def test_profile_currency_symbol_present_when_filtered(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    body = resp.get_data(as_text=True)
    assert "$" in body


def test_profile_currency_symbol_present_on_empty_range(client, demo_id):
    with client.session_transaction() as sess:
        sess["user_id"] = demo_id
        sess["user_name"] = "Demo User"

    resp = client.get(f"/profile?date_from={EMPTY_FROM}&date_to={EMPTY_TO}")
    body = resp.get_data(as_text=True)
    assert "$0.00" in body


# ------------------------------------------------------------------ #
# GET /profile — new user with no expenses, filter applied            #
# ------------------------------------------------------------------ #

def test_profile_new_user_with_filter_shows_empty_state(client, empty_user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = empty_user_id
        sess["user_name"] = "Newcomer"

    resp = client.get(f"/profile?date_from={RANGE_FROM}&date_to={RANGE_TO}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "$0.00" in body
    assert "No transactions yet." in body
