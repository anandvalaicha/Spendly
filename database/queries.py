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


def get_summary_stats(user_id):
    """Return ``{total_spent, transaction_count, top_category}`` for a user.

    A user with no expenses returns zeros and ``top_category`` ``"—"``.
    ``total_spent`` is numeric; the caller formats it for display.
    """
    # --- IMPLEMENTED BY SUBAGENT 2 (summary stats) ---
    raise NotImplementedError


def get_recent_transactions(user_id, limit=10):
    """Return up to ``limit`` of the user's expenses, newest first.

    Each item is ``{date, description, category, amount}`` with the raw ``date``
    string and numeric ``amount``. A user with no expenses returns ``[]``.
    """
    # --- IMPLEMENTED BY SUBAGENT 1 (transaction history) ---
    raise NotImplementedError


def get_category_breakdown(user_id):
    """Return the user's per-category spend as a list of ``{name, amount, pct}``.

    Ordered by ``amount`` descending. ``pct`` is an integer percentage of the
    grand total; the largest category absorbs any rounding remainder so the
    percentages sum to exactly 100. A user with no expenses returns ``[]``.
    """
    # --- IMPLEMENTED BY SUBAGENT 3 (category breakdown) ---
    raise NotImplementedError
