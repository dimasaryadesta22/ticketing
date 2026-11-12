from flask import Blueprint, current_app, jsonify

from ..db import get_db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Dipakai Smoke Test di Jenkins dan healthcheck container."""
    try:
        get_db().scalar("SELECT 1 AS ok")
        db_status = "up"
    except Exception as exc:  # database mati / tidak bisa dihubungi
        current_app.logger.error("Health check: database error: %s", exc)
        db_status = "down"

    body = {
        "status": "ok" if db_status == "up" else "error",
        "database": db_status,
        "version": current_app.config["APP_VERSION"],
    }
    return jsonify(body), (200 if db_status == "up" else 503)
