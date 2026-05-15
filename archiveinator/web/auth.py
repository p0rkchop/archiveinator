"""Authentication utilities: password hashing, session management, user dependency."""

from __future__ import annotations

from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status

from archiveinator.web.db import get_session
from archiveinator.web.models import User


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Returns a string suitable for DB storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def login_user(request: Request, user_id: int, username: str) -> None:
    """Set the user's session, clearing any pre-existing data first."""
    request.session.clear()
    request.session["user_id"] = user_id
    request.session["username"] = username


def logout_user(request: Request) -> None:
    """Clear the user's session."""
    request.session.clear()


def get_current_user(request: Request, db: Any = Depends(get_session)) -> User:
    """FastAPI dependency: returns the authenticated user or raises 401."""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user  # type: ignore[no-any-return]
