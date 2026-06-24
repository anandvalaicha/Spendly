import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_app, init_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
init_app(app)

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
    # Subagent 1 fills this region: build `transactions` (list of dicts with
    # date/description/category/amount/slug) from get_recent_transactions(user_id).
    transactions = []

    # --- summary ---
    # Subagent 2 fills this region: build `summary` (total_spent/transaction_count/
    # top_category, total_spent formatted for display) from get_summary_stats(user_id).
    summary = {"total_spent": "0.00", "transaction_count": 0, "top_category": "—"}

    # --- categories ---
    # Subagent 3 fills this region: build `categories` (list of dicts with
    # name/amount/percent/slug) from get_category_breakdown(user_id).
    categories = []

    return render_template(
        "profile.html",
        user=user, summary=summary,
        transactions=transactions, categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
