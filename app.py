import os
import re
import sqlite3
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_app, init_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
init_app(app)

# Fixed set of expense categories offered in the add-expense form. Used both to
# render the <select> and to validate submitted values.
CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)

with app.app_context():
    init_db()


@app.context_processor
def inject_current_user():
    """Expose the logged-in user to every template for session-aware nav."""
    if "user_id" in session:
        current_user = {"id": session["user_id"], "name": session.get("user_name")}
    else:
        current_user = None
    return {"current_user": current_user}


@app.context_processor
def inject_asset_version():
    """Expose the stylesheet's mtime so templates can cache-bust the CSS link.

    The browser refetches ``style.css`` whenever the file changes instead of
    serving a stale cached copy.
    """
    css_path = os.path.join(app.static_folder, "css", "style.css")
    try:
        version = int(os.path.getmtime(css_path))
    except OSError:
        version = 0
    return {"asset_version": version}


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def slugify(name):
    """Lowercase, hyphenated, alphanumeric slug for category CSS classes.

    Drives the ``tx-badge--<slug>`` / ``cat-fill--<slug>`` classes. Categories
    without a matching class (anything beyond rent/groceries/dining/transport)
    simply fall back to the default badge/bar styling.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower())
    return slug.strip("-")


def parse_iso_date(value):
    """Return a valid ``YYYY-MM-DD`` string unchanged, or ``None`` if malformed.

    Used to validate the ``date_from`` / ``date_to`` query params so a bad URL
    degrades to an unfiltered view instead of raising.
    """
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


def subtract_months(d, months):
    """Return ``d`` shifted back ``months`` calendar months, clamping the day.

    Avoids a ``dateutil`` dependency. The day is clamped to the last valid day
    of the target month (e.g. 31 Mar minus 1 month -> 28/29 Feb).
    """
    month_index = (d.year * 12 + (d.month - 1)) - months
    year, month = divmod(month_index, 12)
    month += 1
    # Last day of the target month: day 1 of the next month minus one day.
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - date.resolution).day
    return date(year, month, min(d.day, last_day))


def build_presets(today):
    """Return the quick-select preset ranges as ``{key: (from, to) or None}``.

    "All Time" maps to ``None`` (no params / clean URL). Computed in the view —
    never in the template.
    """
    today_str = today.strftime("%Y-%m-%d")
    return {
        "this_month": (today.replace(day=1).strftime("%Y-%m-%d"), today_str),
        "last_3_months": (subtract_months(today, 3).strftime("%Y-%m-%d"), today_str),
        "last_6_months": (subtract_months(today, 6).strftime("%Y-%m-%d"), today_str),
        "all_time": None,
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name:
        return render_template("register.html", error="Name is required.")
    if not email:
        return render_template("register.html", error="Email is required.")
    if not password:
        return render_template("register.html", error="Password is required.")
    if not confirm_password:
        return render_template("register.html", error="Please confirm your password.")
    if "@" not in email:
        return render_template(
            "register.html", error="Please enter a valid email address."
        )
    if len(password) < 8:
        return render_template(
            "register.html", error="Password must be at least 8 characters."
        )
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return render_template(
            "register.html", error="An account with that email already exists."
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = "Invalid email or password."

    if not email or not password:
        return render_template("login.html", error=error)

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if user is None or not check_password_hash(user["password"], password):
        return render_template("login.html", error=error)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]

    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # --- date filter ---
    # Both bounds must be present and valid ISO dates for a filter to apply; a
    # missing or malformed value degrades to an unfiltered ("All Time") view.
    date_from = parse_iso_date(request.args.get("date_from"))
    date_to = parse_iso_date(request.args.get("date_to"))

    # ``date_from`` / ``date_to`` keep the user's validated input for redisplay
    # in the form; ``range_from`` / ``range_to`` are what actually drive the
    # queries — left as ``None`` unless a complete, valid, ordered range exists.
    error = None
    if date_from and date_to and date_from > date_to:
        error = "Start date must be before end date."
        range_from = range_to = None
    else:
        range_from = date_from if (date_from and date_to) else None
        range_to = date_to if (date_from and date_to) else None

    presets = build_presets(date.today())
    current_range = (range_from, range_to)
    active_preset = next(
        (key for key, bounds in presets.items()
         if bounds == current_range
         or (bounds is None and range_from is None)),
        None,
    )

    # --- user info ---
    record = get_user_by_id(user_id)
    # Stale session pointing at a deleted user — sign them out cleanly.
    if record is None:
        session.clear()
        return redirect(url_for("login"))

    name = record["name"]
    parts = name.split()
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    else:
        initials = name[:2].upper()

    user = {
        "name": name,
        "email": record["email"],
        "initials": initials,
        "member_since": record["member_since"],
    }

    # --- transactions ---
    # Shape the recent expenses for display: friendly date, 2dp amount, and a
    # CSS slug for the category badge.
    transactions = []
    for row in get_recent_transactions(user_id, date_from=range_from, date_to=range_to):
        try:
            display_date = datetime.strptime(
                row["date"], "%Y-%m-%d"
            ).strftime("%b %d, %Y")
        except ValueError:
            display_date = row["date"]
        transactions.append({
            "date": display_date,
            "description": row["description"],
            "category": row["category"],
            "amount": "%.2f" % row["amount"],
            "slug": slugify(row["category"]),
        })

    # --- summary ---
    # Format the numeric total for display; pass count and top category through.
    stats = get_summary_stats(user_id, date_from=range_from, date_to=range_to)
    summary = {
        "total_spent": "{:,.2f}".format(stats["total_spent"]),
        "transaction_count": stats["transaction_count"],
        "top_category": stats["top_category"],
    }

    # --- categories ---
    # Map the breakdown to the template shape: 2dp amount, `pct` -> `percent`,
    # and a CSS slug for the bar fill.
    categories = [
        {
            "name": cat["name"],
            "amount": "%.2f" % cat["amount"],
            "percent": cat["pct"],
            "slug": slugify(cat["name"]),
        }
        for cat in get_category_breakdown(user_id, date_from=range_from, date_to=range_to)
    ]

    return render_template(
        "profile.html",
        user=user, summary=summary,
        transactions=transactions, categories=categories,
        presets=presets, active_preset=active_preset,
        date_from=date_from or "", date_to=date_to or "",
        error=error,
    )


@app.route("/analytics")
def analytics():
    # Logged-out users hitting this URL directly are bounced to the login page,
    # mirroring the session guard used by the profile route above.
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    # Logged-out users are bounced to login for both GET and POST, mirroring the
    # session guard used by profile() / analytics().
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            amount="",
            category="",
            description="",
            date=date.today().strftime("%Y-%m-%d"),
        )

    # --- POST: validate and insert ---
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date_raw = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    # Values passed back so a failed submission redisplays what the user typed.
    form_values = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description,
    }

    def reject(message):
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            error=message,
            **form_values,
        )

    if not amount_raw:
        return reject("Amount is required.")
    try:
        amount = float(amount_raw)
    except ValueError:
        return reject("Amount must be a number.")
    if amount <= 0:
        return reject("Amount must be greater than zero.")

    if not category:
        return reject("Category is required.")
    if category not in CATEGORIES:
        return reject("Please choose a valid category.")

    if not date_raw:
        return reject("Date is required.")
    if parse_iso_date(date_raw) is None:
        return reject("Please enter a valid date.")

    insert_expense(
        session["user_id"],
        amount,
        category,
        date_raw,
        description[:200] or None,
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
