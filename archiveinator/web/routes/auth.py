"""Authentication routes: register, login, logout."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from archiveinator.config import DEFAULT_PIPELINE
from archiveinator.web.auth import (
    hash_password,
    login_user,
    logout_user,
    verify_password,
)
from archiveinator.web.db import get_session
from archiveinator.web.models import User, UserConfig

router = APIRouter(tags=["auth"])


@router.get("/auth/register", response_class=HTMLResponse)
async def register_form() -> Response:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Register — archiveinator</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="auth-page">
<div class="auth-container">
<h1>archiveinator</h1>
<h2>Create Account</h2>
<form method="post" action="/auth/register">
<div class="form-group">
<label for="username">Username</label>
<input type="text" id="username" name="username" required autofocus>
</div>
<div class="form-group">
<label for="email">Email (optional, for notifications)</label>
<input type="email" id="email" name="email">
</div>
<div class="form-group">
<label for="password">Password</label>
<input type="password" id="password" name="password" required minlength="8">
</div>
<div class="form-group">
<label for="confirm">Confirm Password</label>
<input type="password" id="confirm" name="confirm" required minlength="8">
</div>
<button type="submit" class="btn btn-primary">Register</button>
</form>
<p class="auth-link">Already have an account? <a href="/auth/login">Log in</a></p>
</div>
</body>
</html>"""
    return HTMLResponse(html)


@router.post("/auth/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    email: str | None = Form(default=None),
    db: Any = Depends(get_session),
) -> Response:
    if password != confirm:
        return html_error("Passwords do not match")

    if len(password) < 8:
        return html_error("Password must be at least 8 characters")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return html_error("Username already taken")

    # First user is admin
    user_count = db.query(User).count()
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        is_admin=(user_count == 0),
    )
    db.add(user)
    db.flush()

    # Create default config
    default_config = UserConfig(
        user_id=user.id,
        pipeline_json=json.dumps(
            [{"step": s.step, "enabled": s.enabled} for s in DEFAULT_PIPELINE]
        ),
    )
    db.add(default_config)

    login_user(request, user.id, user.username)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/auth/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Response:
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=302)
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — archiveinator</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="auth-page">
<div class="auth-container">
<h1>archiveinator</h1>
<h2>Log In</h2>
<form method="post" action="/auth/login">
<div class="form-group">
<label for="username">Username</label>
<input type="text" id="username" name="username" required autofocus>
</div>
<div class="form-group">
<label for="password">Password</label>
<input type="password" id="password" name="password" required>
</div>
<button type="submit" class="btn btn-primary">Log In</button>
</form>
<p class="auth-link">Don't have an account? <a href="/auth/register">Register</a></p>
</div>
</body>
</html>"""
    return HTMLResponse(html)


@router.post("/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Any = Depends(get_session),
) -> Response:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return html_error("Invalid username or password")

    login_user(request, user.id, user.username)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/auth/logout")
async def logout(request: Request) -> Response:
    logout_user(request)
    return RedirectResponse(url="/auth/login", status_code=302)


def html_error(message: str) -> HTMLResponse:
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Error — archiveinator</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="auth-page">
<div class="auth-container">
<h1>archiveinator</h1>
<div class="error-message">{message}</div>
<p><a href="javascript:history.back()">Go back</a></p>
</div>
</body>
</html>""",
        status_code=400,
    )
