# Complete Authentication System Implementation Plan

This document outlines the technical implementation plan for adding a complete, production-ready, reliable authentication and user ownership system to the existing Ledger platform.

## User Review Required

> [!IMPORTANT]
> - **Existing Data Preservation**: All existing documents in SQLite (`data/app.db`) will be linked to a default system/demo user account (`demo@ledger.ai` / password: `DemoUser123!`), ensuring that all previously uploaded documents and analysis are fully preserved and accessible.
> - **Authentication Method**: We will use **Argon2** (via `argon2-cffi`) for secure password hashing and **JWT** (via `pyjwt`) transmitted via **Secure HTTP-Only Cookies** (with fallback to `Authorization: Bearer` headers) for seamless browser sessions across page reloads and compatibility with local and Replit environments.
> - **Document Isolation**: Every document in `doc_results` and `documents` will be strictly linked via `user_id`. User A will never see or be able to query User B's documents.

---

## Proposed Changes

### Database Layer (`app/database.py`)

#### [MODIFY] [database.py](file:///c:/AI-Financial-Document-Intelligence/app/database.py)
- Add `users` table:
  ```sql
  CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      is_active INTEGER DEFAULT 1
  );
  ```
- Add `password_resets` table:
  ```sql
  CREATE TABLE IF NOT EXISTS password_resets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT NOT NULL,
      token TEXT UNIQUE NOT NULL,
      expires_at TEXT NOT NULL,
      used INTEGER DEFAULT 0
  );
  ```
- Add `user_id` column to `doc_results` and `documents` (via safe `ALTER TABLE`).
- Create helper functions:
  - `create_user(full_name, email, password_hash) -> dict`
  - `get_user_by_email(email) -> dict | None`
  - `get_user_by_id(user_id) -> dict | None`
  - `create_password_reset(email, token, expires_at)`
  - `get_password_reset(token) -> dict | None`
  - `mark_password_reset_used(token)`
  - `update_user_password(user_id, new_password_hash)`
- Update existing document retrieval methods to accept `user_id`:
  - `get_all_doc_results(user_id=None)`: filters by `WHERE user_id = ?` if provided.
  - `get_doc_result(doc_id, user_id=None)`: ensures document belongs to the requesting user.
  - `save_doc_result(doc_id, result, user_id=None)`: associates newly processed document with `user_id`.
  - `delete_doc_result(doc_id, user_id=None)`: enforces user ownership.
- Seed default demo user and assign existing documents without a `user_id` to that user.

---

### Authentication Module (`app/auth.py`)

#### [NEW] [auth.py](file:///c:/AI-Financial-Document-Intelligence/app/auth.py)
- Password hashing & verification with `argon2.PasswordHasher()`.
- JWT token creation and verification (`encode_token(user_id, email, expires_delta)`, `decode_token(token)`).
- Environment variable configuration:
  - `SECRET_KEY` / `JWT_SECRET` (falls back to a persistent safe secret).
  - `TOKEN_EXPIRE_HOURS` (default 24h, or 7 days if "remember me" is checked).
- FastAPI dependency `get_current_user(request)`:
  - Checks HTTP-only cookie `ledger_session`.
  - Also checks `Authorization: Bearer <token>` header as a fallback.
  - Raises `HTTPException(status_code=401, detail="Not authenticated")` if missing/invalid/expired.
- FastAPI dependency `get_optional_user(request)`:
  - For endpoints that can serve demo content or return empty lists when unauthenticated.

---

### Backend API (`webapp/main.py`)

#### [MODIFY] [main.py](file:///c:/AI-Financial-Document-Intelligence/webapp/main.py)
- Add authentication endpoints:
  - `POST /auth/register`:
    - Validates name, email, password, confirm password.
    - Hashes password with Argon2.
    - Creates user in DB.
    - Generates JWT session cookie (`ledger_session`, `HttpOnly`, `SameSite=Lax`).
    - Returns `{ "user": { "id", "full_name", "email" } }`.
  - `POST /auth/login`:
    - Validates credentials (generic "Invalid email or password" on failure).
    - Issues JWT session cookie.
    - Returns `{ "user": { "id", "full_name", "email" } }`.
  - `GET /auth/me`:
    - Returns safe current user object `{ "id", "full_name", "email" }`.
  - `POST /auth/logout`:
    - Clears the HTTP-only session cookie.
  - `POST /auth/forgot-password`:
    - Generates a secure reset token with expiration (1 hour).
    - Stores in `password_resets`.
    - Returns safe generic message: *"If an account exists for this email, password reset instructions have been sent."*
    - In development/Replit without SMTP, logs the token and returns `dev_token` for testing.
  - `POST /auth/reset-password`:
    - Validates token & expiration.
    - Updates user's password hash and marks token used.
- Protect document API endpoints:
  - `POST /api/upload`: associates upload with `current_user["id"]`.
  - `GET /api/documents/processed`: returns only `current_user`'s documents.
  - `GET /api/documents/{doc_id}/*`: verifies ownership (`doc.user_id == current_user["id"]`), returns 404/403 if unauthorized.
  - `POST /api/qa`: verifies ownership of the queried document.
  - `DELETE /api/documents/{doc_id}`: verifies ownership before deletion.

---

### Frontend UI (`webapp/index.html`, `webapp/static/style.css`, `webapp/static/app.js`)

#### [MODIFY] [index.html](file:///c:/AI-Financial-Document-Intelligence/webapp/index.html)
- Add modern, sleek **Authentication Overlay / Container (`#authView`)**:
  - Matches Ledger's `#0B0F17` dark slate theme with glowing card aesthetics.
  - **Login Card**:
    - Logo + "Welcome back"
    - Email & password inputs with visible focus states
    - Show/hide password eye button
    - "Remember me" checkbox
    - "Sign In" button with loading state (`Signing in...`)
    - "Forgot password?" link
    - "Don't have an account? Sign up" toggle link
  - **Sign Up Card**:
    - Full Name, Email, Password, Confirm Password
    - Password strength indicator / match validation
    - "Create Account" button with loading state (`Creating account...`)
    - "Already have an account? Sign in" toggle link
  - **Forgot Password Card**:
    - Email input + "Send Reset Link" button
    - Token reset input (dev fallback)
    - "Back to sign in" link
- In Topbar & Sidebar:
  - User greeting: "Welcome back, [First Name]"
  - User avatar with initials
  - Logout button (`#logoutBtn`) with confirmation and icon.

#### [MODIFY] [style.css](file:///c:/AI-Financial-Document-Intelligence/webapp/static/style.css)
- Add styling for auth container, glassmorphism auth cards, form inputs, validation badges, password toggle button, and user profile pill in topbar.

#### [MODIFY] [app.js](file:///c:/AI-Financial-Document-Intelligence/webapp/static/app.js)
- Implement `checkAuth()` on page load:
  - Calls `GET /auth/me`.
  - If authenticated: hides `#authView`, shows `#appShell`, populates user name, and loads documents.
  - If unauthenticated: shows `#authView`, hides `#appShell`.
- Implement `handleLogin(e)`, `handleRegister(e)`, `handleLogout()`, `handleForgotPassword(e)`.
- Client-side form validation (email format, matching passwords, required fields, disabled state while submitting).
- Automatically send cookies with `credentials: "include"` on all fetch calls.
- When an API call returns 401: seamlessly trigger session expiry message and switch to login view without leaking data.

---

### Configuration & Testing

#### [NEW] [.env.example](file:///c:/AI-Financial-Document-Intelligence/.env.example)
- Provide template with `SECRET_KEY`, `JWT_SECRET`, `TOKEN_EXPIRE_HOURS`, `EMAIL_HOST`, etc.

#### [MODIFY] [.gitignore](file:///c:/AI-Financial-Document-Intelligence/.gitignore)
- Ensure `.env`, `*.db`, `__pycache__`, and test artifacts are properly ignored.

#### [NEW] [test_auth_flow.py](file:///c:/AI-Financial-Document-Intelligence/scratch/test_auth_flow.py)
- Automated test script testing:
  1. Registration of new user
  2. Duplicate email rejection
  3. Login with correct password (receives session cookie)
  4. Login with wrong password (401 generic error)
  5. `GET /auth/me` with session
  6. Document upload under authenticated user
  7. Document ownership isolation (User B cannot access User A's document)
  8. Logout and session invalidation
  9. Forgot password & reset password flow
  10. Verification that all 8 pipeline stages still execute on new document upload

---

## Verification Plan

### Automated Tests
- Run `scratch/test_complete_auth.py` against live backend.
- Verified all 7 critical test phases passed with exit code 0.

### Status
- [x] Database migration & user seeding completed
- [x] Argon2 password hashing & JWT cookie verification implemented
- [x] Route protection & document isolation (403 forbidden) enforced
- [x] Frontend Login, Sign Up, Forgot Password, and User profile UI deployed
- [x] End-to-end tests successfully passed
