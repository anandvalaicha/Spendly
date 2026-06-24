"""Pure query helpers for Spendly — Step 5 (Backend Connection).

Each helper reads the SQLite database via ``get_db()`` and returns plain Python
data structures (no Flask request/response objects). Display formatting — money
strings, dates, CSS slugs — is the caller's job (see ``profile()`` in ``app.py``).

All queries are parameterised and scoped to a single ``user_id`` so one user can
never read another's expenses.

Note on connections: ``get_db()`` caches one connection on Flask's ``g`` for the
whole request, and several of these helpers run within a single ``/profile``
request, so they must NOT close that shared connection — the ``close_db``
teardown registered by ``init_app()`` handles it.
"""

from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return ``(sql_fragment, params)`` for an inclusive date-range filter.

    When both bounds are provided the fragment is ``" AND date BETWEEN ? AND ?"``
    with the two values as parameters; otherwise an empty fragment and no params,
    so callers behave exactly as if no filter were applied. The bounds are always
    passed as query parameters — never string-formatted into the SQL.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", [date_from, date_to]
    return "", []


def get_user_by_id(user_id):
    """Return ``{name, email, member_since}`` for a user, or ``None``.

    ``member_since`` is derived from ``users.created_at`` and formatted as
    ``"Month YYYY"`` (e.g. "June 2026"), falling back to the raw value if it
    cannot be parsed.
    """
    db = get_db()
    row = db.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        return None

    member_since = row["created_at"] or ""
    try:
        member_since = datetime.strptime(
            member_since[:19], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except ValueError:
        pass

    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


def insert_expense(user_id, amount, category, date, description):
    """Insert one expense scoped to ``user_id``; commit; return the new row id.

    All values are passed as query parameters. ``description`` may be ``None``,
    in which case it is stored as SQL ``NULL``. Note the column order matches the
    schema in ``database/db.py`` (``amount, category, description, date``).
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO expenses (user_id, amount, category, description, date) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, description, date),
    )
    db.commit()
    return cur.lastrowid


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return ``{total_spent, transaction_count, top_category}`` for a user.

    A user with no expenses returns zeros and ``top_category`` ``"—"``.
    ``total_spent`` is numeric; the caller formats it for display. When both
    ``date_from`` and ``date_to`` are given, only expenses whose ``date`` falls
    inside that inclusive range are counted.
    """
    db = get_db()
    date_sql, date_params = _date_clause(date_from, date_to)

    row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?" + date_sql,
        [user_id] + date_params,
    ).fetchone()

    top = db.execute(
        "SELECT category FROM expenses WHERE user_id = ?" + date_sql
        + " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        [user_id] + date_params,
    ).fetchone()

    return {
        "total_spent": row["total"],
        "transaction_count": row["count"],
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return up to ``limit`` of the user's expenses, newest first.

    Each item is ``{date, description, category, amount}`` with the raw ``date``
    string and numeric ``amount``. A user with no expenses returns ``[]``. When
    both ``date_from`` and ``date_to`` are given, only expenses inside that
    inclusive range are returned.
    """
    db = get_db()
    date_sql, date_params = _date_clause(date_from, date_to)
    rows = db.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ?" + date_sql + " ORDER BY date DESC, id DESC LIMIT ?",
        [user_id] + date_params + [limit],
    ).fetchall()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return the user's per-category spend as a list of ``{name, amount, pct}``.

    Ordered by ``amount`` descending. ``pct`` is an integer percentage of the
    grand total; the largest category absorbs any rounding remainder so the
    percentages sum to exactly 100. A user with no expenses returns ``[]``. When
    both ``date_from`` and ``date_to`` are given, only expenses inside that
    inclusive range are counted.
    """
    db = get_db()
    date_sql, date_params = _date_clause(date_from, date_to)
    rows = db.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ?" + date_sql + " GROUP BY category ORDER BY total DESC",
        [user_id] + date_params,
    ).fetchall()

    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total == 0:
        return []

    result = [
        {"name": row["category"], "amount": row["total"],
         "pct": int(round(row["total"] * 100 / grand_total))}
        for row in rows
    ]

    # Make the percentages sum to exactly 100 by adjusting the largest
    # category (the first one, since rows are ordered by total descending).
    result[0]["pct"] = 100 - sum(cat["pct"] for cat in result[1:])

    return result
