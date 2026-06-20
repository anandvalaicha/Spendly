# Spec: Registration

## Overview

Turn the existing `/register` page into a working sign-up flow. Previously, the route only rendered `register.html`. The form already POSTs to `/register`, but nothing handled the submitted data.

This step adds server-side handling: validate the submitted name, email and password, hash the password with werkzeug, insert a new row into the `users` table, and redirect to the login page on success.

This is the first feature that writes user data and is the entry point to every authenticated feature that follows, including login, profile and expenses.

## Depends on

- Step 1 — Database setup
  - `database/db.py` provides `get_db`, `init_db`, and `init_app`.
  - The `users` table must exist before a registration can be inserted.

## Routes

- `GET /register` — render the registration form — public
- `POST /register` — validate input, create the user, redirect to `/login` on success, or re-render the form with an error — public

No additional routes are introduced.

## Database changes

No database changes are required. This feature uses the existing `users` table from Step 1:

| Column     | Type    | Notes                      |
| ---------- | ------- | -------------------------- |
| id         | INTEGER | PK, autoincrement          |
| name       | TEXT    | not null                   |
| email      | TEXT    | not null, UNIQUE           |
| password   | TEXT    | not null — stores the hash |
| created_at | TEXT    | default `datetime('now')`  |

Note: the column is named `password`, but it stores the hashed password, not the plaintext password.

The UNIQUE constraint on `email` is relied on to prevent duplicate accounts.

## Templates

- Create: none.
- Modify: none required.

`templates/register.html` already:

- extends `base.html`
- renders an `{% if error %}` block
- posts to `/register`
- collects `name`, `email` and `password`

## Files to change

### `app.py`

Update the existing `register` view so it accepts both `GET` and `POST`.

On `POST`, it must:

1. Read `name`, `email` and `password` from the submitted form.
2. Strip surrounding whitespace from all three values.
3. Validate the submitted values.
4. Lowercase the email before storing it.
5. Hash the password using `werkzeug.security.generate_password_hash`.
6. Insert the new user into the existing `users` table.
7. Commit the transaction after a successful insert.
8. Redirect to `/login` on success.
9. Catch duplicate email errors using `sqlite3.IntegrityError`.
10. Roll back the transaction if the insert fails.
11. Re-render `register.html` with a clear error message on validation or duplicate email failure.

Also update imports in `app.py` as needed:

- `sqlite3`
- `request`
- `redirect`
- `url_for`
- `generate_password_hash`
- `get_db`
- `init_db`
- `init_app`

Wire the database into the app on startup:

- call `init_app(app)`
- call `init_db()` inside an app context

This ensures the `users` table exists when a registration is submitted.

## Files to create

No new files.

## New dependencies

No new dependencies.

This feature uses:

- `werkzeug.security.generate_password_hash`
- Python standard library `sqlite3`

## Rules for implementation

- No SQLAlchemy or ORMs.
- Use `get_db()` and raw SQL only.
- Use parameterised queries only.
- Never use string formatting or f-strings inside SQL statements.
- Passwords must be hashed with werkzeug.
- Use `generate_password_hash` with method `pbkdf2:sha256`, matching the seed data.
- Never store the plaintext password.
- Insert the hashed password into the existing `password` column.
- The stored password value must not equal the submitted plaintext password.
- Use CSS variables only. Do not hardcode hex values.
- All templates must extend `base.html`.
- `register.html` already extends `base.html`.
- Re-render `register.html` with a clear `error` message on any validation failure.
- Do not crash on duplicate email.
- Catch `sqlite3.IntegrityError` for duplicate email and show a friendly message.
- Call `db.commit()` after a successful insert.
- Call `db.rollback()` if the insert fails.

## Validation rules

On `POST /register`:

- `name`, `email` and `password` are all required.
- All three values must be stripped of surrounding whitespace.
- Reject the request if any field is empty.
- `email` must contain an `@`.
- `email` must be stored lowercased.
- `password` must be at least 8 characters.
- Duplicate email must be rejected using the `users.email` UNIQUE constraint.
- On duplicate email, catch `sqlite3.IntegrityError`, roll back the transaction, and show:

`An account with that email already exists.`

- On success, redirect to `/login`.
- Use the PRG pattern on success.
- Do not re-render the form after successful registration.

## Error messages

Use clear error messages when validation fails:

| Scenario                           | Error message                                |
| ---------------------------------- | -------------------------------------------- |
| Missing name                       | `Name is required.`                          |
| Missing email                      | `Email is required.`                         |
| Missing password                   | `Password is required.`                      |
| Invalid email                      | `Please enter a valid email address.`        |
| Password shorter than 8 characters | `Password must be at least 8 characters.`    |
| Duplicate email                    | `An account with that email already exists.` |

## Definition of done

- [ ] App starts without errors.
- [ ] The `users` table exists at runtime.
- [ ] `GET /register` still renders the registration form.
- [ ] `POST /register` accepts valid registration details.
- [ ] Submitting valid details creates exactly one new row in `users`.
- [ ] The stored password is hashed and is not plaintext.
- [ ] The stored password verifies against the original password using `werkzeug.security.check_password_hash`.
- [ ] Successful registration redirects to `/login`.
- [ ] Submitting an email that already exists re-renders the form with a visible error.
- [ ] Duplicate email creates no new row.
- [ ] Submitting with a missing field re-renders the form with a visible error.
- [ ] Submitting a password shorter than 8 characters is rejected with a visible error.
- [ ] All SQL uses parameterised queries.
- [ ] No SQLAlchemy or ORM is used.
