"""Autentikasi berbasis token (Authorization: Bearer <token>)."""
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .db import get_db
from .errors import ApiError


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="tiketin-auth")


def issue_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})


def _current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Login terlebih dahulu (header Authorization: Bearer <token>)")
    token = header[len("Bearer "):].strip()
    try:
        data = _serializer().loads(token, max_age=current_app.config["TOKEN_MAX_AGE_SECONDS"])
    except SignatureExpired:
        raise ApiError(401, "TOKEN_EXPIRED", "Token kedaluwarsa, silakan login ulang")
    except BadSignature:
        raise ApiError(401, "UNAUTHORIZED", "Token tidak valid")
    user = get_db().one(
        "SELECT id, name, email, is_admin FROM users WHERE id = ?", (data.get("uid"),)
    )
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Akun tidak ditemukan")
    user["is_admin"] = bool(user["is_admin"])
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = _current_user()
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = _current_user()
        if not g.user["is_admin"]:
            raise ApiError(403, "FORBIDDEN", "Hanya admin yang boleh mengelola event")
        return view(*args, **kwargs)

    return wrapper
