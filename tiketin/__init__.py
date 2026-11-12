"""Tiketin — platform penjualan tiket event berkuota (Studi Kasus K02)."""
from flask import Flask

from .config import Config
from .db import close_db
from .errors import register_error_handlers


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    from .routes import health

    app.register_blueprint(health.bp)

    app.teardown_appcontext(close_db)
    register_error_handlers(app)
    return app
