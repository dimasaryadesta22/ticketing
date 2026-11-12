"""Perintah administrasi:

    python manage.py migrate   # jalankan migrasi database
    python manage.py seed      # isi data contoh (admin, pembeli demo, 3 event)
"""
import sys

from tiketin import create_app
from tiketin.db import connect_with_retry, run_migrations
from tiketin.seed import run_seed


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("migrate", "seed"):
        print(__doc__)
        return 1

    app = create_app()
    with app.app_context():
        conn = connect_with_retry(app.config["DATABASE_URL"])
        try:
            if argv[1] == "migrate":
                done = run_migrations(conn)
                print(f"[migrate] {len(done)} migrasi dijalankan: {done or '-'}")
            else:
                for line in run_seed(conn, app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"]):
                    print(f"[seed] {line}")
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
