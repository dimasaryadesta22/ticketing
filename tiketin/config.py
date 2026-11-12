"""Konfigurasi aplikasi. Semua nilai rahasia diambil dari environment variable (.env)."""
import os


class Config:
    # Contoh: postgresql://tiketin:rahasia@db:5432/tiketin  atau  sqlite:///tiketin.db
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tiketin-dev.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-ganti-di-env")
    APP_VERSION = os.getenv("APP_VERSION", "dev")
    TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")

    # Aturan bisnis
    MAX_TICKETS_PER_ACCOUNT = 4      # satu akun maksimal 4 tiket per event
    CANCEL_DEADLINE_DAYS = 1         # pembatalan hanya boleh sebelum H-1

    TOKEN_MAX_AGE_SECONDS = 7 * 24 * 3600

    # Akun admin awal (dibuat oleh seeder)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@tiketin.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
