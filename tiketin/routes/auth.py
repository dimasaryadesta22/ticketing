import re

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import issue_token, login_required
from ..db import get_db
from ..errors import ApiError, ValidationError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_json(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "email": u["email"], "is_admin": bool(u["is_admin"])}


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not name or len(name) > 100:
        raise ValidationError("Nama wajib diisi (maks. 100 karakter)")
    if not EMAIL_RE.match(email):
        raise ValidationError("Format email tidak valid")
    if len(password) < 8:
        raise ValidationError("Password minimal 8 karakter")

    db = get_db()
    if db.one("SELECT id FROM users WHERE email = ?", (email,)):
        raise ApiError(409, "EMAIL_TAKEN", "Email sudah terdaftar")
    try:
        user = db.one(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?) RETURNING *",
            (name, email, generate_password_hash(password)),
        )
    except db.IntegrityError:
        raise ApiError(409, "EMAIL_TAKEN", "Email sudah terdaftar")
    return jsonify(user=_user_json(user), token=issue_token(user["id"])), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    user = get_db().one("SELECT * FROM users WHERE email = ?", (email,))
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email atau password salah")
    return jsonify(user=_user_json(user), token=issue_token(user["id"]))


@bp.get("/me")
@login_required
def me():
    return jsonify(user=_user_json(g.user))
