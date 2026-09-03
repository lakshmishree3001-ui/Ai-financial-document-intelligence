"""
app/auth.py - Authentication, Password Security & Session Management
===================================================================
Provides:
  - State-of-the-art password hashing using Argon2 (OWASP recommended)
  - JWT creation, verification, and decoding (pyjwt)
  - Secure HTTP-Only cookie and Authorization header parsing
  - FastAPI dependencies for route and endpoint protection
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
from fastapi import Request, HTTPException, status

import database as db

# Password hasher instance (Argon2id default parameters)
_hasher = PasswordHasher()

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "ledger-ai-financial-intelligence-jwt-secret-key-2026"
ALGORITHM = "HS256"
DEFAULT_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))
REMEMBER_EXPIRE_DAYS = 7
COOKIE_NAME = "ledger_session"


def hash_password(password: str) -> str:
    """Hash a plain text password using Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty.")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2 hash. Returns True if valid, False otherwise."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
    except Exception:
        return False


def create_access_token(user_id: int, email: str, remember_me: bool = False) -> str:
    """Create a signed JWT access token with user claims and expiration."""
    now = datetime.now(timezone.utc)
    if remember_me:
        expire = now + timedelta(days=REMEMBER_EXPIRE_DAYS)
    else:
        expire = now + timedelta(hours=DEFAULT_EXPIRE_HOURS)

    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token. Returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
    except Exception:
        return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract token from either HTTP-only cookie or Authorization header."""
    # 1. Primary: HTTP-Only cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # 2. Secondary: Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency: Enforces that the user has a valid authenticated session.
    Raises HTTPException(401) if missing, invalid, or expired.
    Returns safe user dict: {'id', 'full_name', 'email'}.
    """
    token = extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or not payload.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get_user_by_id(int(payload["user_id"]))
    if not user or not user.get("is_active", 1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return safe user fields (never return password_hash)
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
    }


async def get_optional_user(request: Request) -> Optional[dict]:
    """
    FastAPI dependency: Returns the authenticated user if present, or None if not.
    Does NOT raise 401.
    """
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
