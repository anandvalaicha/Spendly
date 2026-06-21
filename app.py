import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_app, init_db

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
    return "Profile page — coming in Step 4"


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
