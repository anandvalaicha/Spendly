# Spec: Login and Logout

## Overview

Turn the existing `/login` page into a working sign-in flow and implement
`/logout`. Today `/login` only renders `login.html` on `GET` and `/logout` is a
placeholder that returns the string `"Logout — coming in Step 3"`. This step
adds server-side authentication: verify the submitted email and password against
the hashed password stored in the `users` table, establish a server-side session
on success, and clear that session on logout. Registration (Step 2) already
creates users and redirects to `/login`; this is the step that lets those users
actually sign in, and it is the gateway to every logged-in feature that follows
(profile in Step 4, expenses from Step 7 onward).

## Depends on

- Step 1 — Database setup: `database/db.py` provides `get_db`, `init_db`, and
  `init_app`, and the `users` table holds `id`, `name`, `email`, and the hashed
  `password`.
- Step 2 — Registration: `POST /register` creates users with a werkzeug hash
  (`pbkdf2:sha256`) stored in the `password` column, so there are real accounts
  to sign in with.

## Routes

- `GET /login` — render the sign-in form — public
- `POST /login` — validate credentials, create a session, redirect to the
  profile page on success, or re-render the form with an error — public
- `GET /logout` — clear the session and redirect to the landing page — logged-in

The existing `GET /login` and the `/logout` placeholder are both replaced by
working implementations. No other new routes are introduced.

## Database changes

No database changes. This feature reads the existing `users` table from Step 1:

| Column   | Type    | Notes                                  |
| -------- | ------- | -------------------------------------- |
| id       | INTEGER | PK, autoincrement                      |
| name     | TEXT    | not null                               |
| email    | TEXT    | not null, UNIQUE                       |
| password | TEXT    | not null — stores the werkzeug **hash** |

Note: the column is named `password` but stores the hashed value, verified with
`werkzeug.security.check_password_hash`.

## Templates

- **Create:** none. `templates/login.html` already exists, extends `base.html`,
  posts to `/login` with `email` and `password` fields, and renders an
  `{% if error %}` block.
- **Modify:** `templates/base.html` — make the nav links session-aware. When a
  user is logged in, show their name (or a "Profile" link) and a "Sign out" link
  to `{{ url_for('logout') }}`; when logged out, show the existing "Sign in" and
  "Get started" links. Drive this off the session via a value exposed to all
  templates (see `app.py` below).

## Files to change

### `app.py`

1. **Session secret key.** Add `app.secret_key` (read from the `SECRET_KEY`
   environment variable, falling back to a hardcoded dev value) so Flask's signed
   session cookie works. There is currently no secret key configured.
2. **Imports.** Add `session`, `flash` (if used for messaging), and
   `check_password_hash` from `werkzeug.security` alongside the existing
   `generate_password_hash` import.
3. **`POST /login` handling.** Update the `login` view to accept `GET` and
   `POST`. On `POST` it must:
   - Read `email` and `password` from the form; strip whitespace and lowercase
     the email (matching how registration stores it).
   - Validate both fields are present.
   - Look up the user by email with a parameterised query.
   - Verify the submitted password against the stored hash with
     `check_password_hash`.
   - On success, store the user's `id` (and optionally `name`) in `session` and
     redirect to `/profile` using the PRG pattern.
   - On any failure (unknown email or wrong password), re-render `login.html`
     with a single generic error and do **not** reveal which field was wrong.
4. **`/logout` handling.** Replace the placeholder with a view that calls
   `session.clear()` and redirects to `landing`.
5. **Expose login state to templates.** Add a `context_processor` (or equivalent)
   so `base.html` can render the correct nav for logged-in vs logged-out users
   without each view passing the flag manually.

### `templates/base.html`

Update the `.nav-links` block to be session-aware, as described under Templates.

## Files to create

No new files.

## New dependencies

No new dependencies. Uses `flask.session`, `werkzeug.security.check_password_hash`
(werkzeug is already in `requirements.txt`), and the standard library.

## Rules for implementation

- No SQLAlchemy or ORMs — use `get_db()` and raw SQL only.
- Parameterised queries only; never use string formatting or f-strings inside SQL.
- Passwords are verified with werkzeug (`check_password_hash`); never compare
  plaintext passwords and never store or log the submitted password.
- Use CSS variables only — never hardcode hex values (use the tokens defined in
  `static/css/style.css`, e.g. `--danger` for the error state).
- All templates extend `base.html`; `login.html` already does.
- Use a single generic error message for failed sign-in (do not disclose whether
  the email exists).
- Use the PRG pattern on success — redirect, never re-render, after a successful
  login.
- Lowercase and strip the email before lookup so it matches the stored value.
- `app.secret_key` must be set before `session` is used.

## Validation rules

On `POST /login`:

- `email` and `password` are both required; reject the request if either is empty.
- `email` is stripped and lowercased before lookup.
- Look up the user by email; if no row is found, fail.
- If a row is found, verify the password with `check_password_hash`; if it does
  not match, fail.
- On any failure, re-render `login.html` with the error: `Invalid email or password.`
- On success, set the session and redirect to `/profile`.

## Definition of done

- [ ] App starts without errors and `app.secret_key` is configured.
- [ ] `GET /login` renders the sign-in form.
- [ ] `POST /login` with valid credentials for a seeded/registered user creates a
      session and redirects to `/profile`.
- [ ] After login, `session` contains the user's id.
- [ ] `POST /login` with a wrong password re-renders the form with the error
      `Invalid email or password.` and creates no session.
- [ ] `POST /login` with an unknown email shows the same generic error.
- [ ] `POST /login` with a missing field re-renders the form with a visible error.
- [ ] The error message is identical for unknown-email and wrong-password cases.
- [ ] `GET /logout` clears the session and redirects to the landing page.
- [ ] After logout, the session no longer contains the user's id.
- [ ] `base.html` shows "Sign out" / profile when logged in and "Sign in" /
      "Get started" when logged out.
- [ ] All SQL uses parameterised queries.
- [ ] No SQLAlchemy or ORM is used, and no plaintext password comparison occurs.
