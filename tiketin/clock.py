"""Sumber waktu tunggal supaya aturan tanggal (H-1) mudah diuji."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context


def _tz() -> ZoneInfo:
    name = current_app.config["TIMEZONE"] if has_app_context() else "Asia/Jakarta"
    return ZoneInfo(name)


def now() -> datetime:
    return datetime.now(_tz())


def today() -> date:
    return now().date()
