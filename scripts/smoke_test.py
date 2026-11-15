"""Smoke Test: memanggil GET /health aplikasi yang baru di-deploy.

Keluar dengan kode 1 (pipeline gagal) jika respons bukan 200 setelah beberapa kali coba.
Hanya memakai library standar Python, jadi bisa dijalankan di dalam container app:

    docker compose exec -T app python scripts/smoke_test.py
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000/health")
    p.add_argument("--retries", type=int, default=12)
    p.add_argument("--delay", type=float, default=5.0)
    args = p.parse_args()

    for attempt in range(1, args.retries + 1):
        try:
            with urllib.request.urlopen(args.url, timeout=5) as res:
                body = json.loads(res.read().decode() or "{}")
                print(f"[smoke] percobaan {attempt}: HTTP {res.status} {body}")
                if res.status == 200 and body.get("database") == "up":
                    print("[smoke] OK - aplikasi sehat dan terhubung ke database")
                    return 0
        except urllib.error.HTTPError as exc:
            print(f"[smoke] percobaan {attempt}: HTTP {exc.code} {exc.read().decode()[:200]}")
        except Exception as exc:  # koneksi ditolak, timeout, dll.
            print(f"[smoke] percobaan {attempt}: {exc}")
        time.sleep(args.delay)

    print(f"[smoke] GAGAL - {args.url} tidak mengembalikan 200")
    return 1


if __name__ == "__main__":
    sys.exit(main())
