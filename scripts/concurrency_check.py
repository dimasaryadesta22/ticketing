"""Concurrency Check (tantangan DevOps K02).

1. Login sebagai admin dan membuat event baru berkuota 20.
2. Mendaftarkan 50 akun pembeli (satu tiket per akun, supaya batas 4 tiket/akun
   tidak ikut memengaruhi hasil).
3. Mengirim 50 permintaan pembelian SECARA BERSAMAAN (50 thread dilepas serentak).
4. Memastikan tepat 20 pembelian berhasil dan event mencatat sold = 20.

Keluar dengan kode 1 (pipeline gagal) bila terjadi overselling atau hasil tidak sesuai.
Hanya memakai library standar Python:

    docker compose exec -T app python scripts/concurrency_check.py
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta


def call(base, method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read().decode()
            return res.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw[:200]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--requests", type=int, default=50)
    p.add_argument("--quota", type=int, default=20)
    p.add_argument("--admin-email", default=os.getenv("ADMIN_EMAIL", "admin@tiketin.local"))
    p.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD", "admin12345"))
    p.add_argument("--keep-event", action="store_true", help="jangan hapus event uji setelah selesai")
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    run_id = uuid.uuid4().hex[:8]

    status, body = call(base, "POST", "/api/auth/login",
                        {"email": args.admin_email, "password": args.admin_password})
    if status != 200:
        print(f"[concurrency] GAGAL login admin: HTTP {status} {body}")
        return 1
    admin = body["token"]

    event_date = (date.today() + timedelta(days=30)).isoformat()
    status, body = call(base, "POST", "/api/events", {
        "name": f"[Concurrency Check {run_id}]", "event_date": event_date,
        "price": 10000, "quota": args.quota}, admin)
    if status != 201:
        print(f"[concurrency] GAGAL membuat event uji: HTTP {status} {body}")
        return 1
    event_id = body["event"]["id"]
    print(f"[concurrency] event uji #{event_id} dibuat, kuota {args.quota}")

    def register(i):
        s, b = call(base, "POST", "/api/auth/register", {
            "name": f"Pembeli {i}", "email": f"cc-{run_id}-{i}@tiketin.test", "password": "password123"})
        if s != 201:
            raise RuntimeError(f"registrasi akun {i} gagal: HTTP {s} {b}")
        return b["token"]

    with ThreadPoolExecutor(max_workers=10) as pool:
        tokens = list(pool.map(register, range(args.requests)))
    print(f"[concurrency] {len(tokens)} akun pembeli siap")

    gate = threading.Barrier(args.requests)

    def purchase(token):
        gate.wait()  # semua thread mengirim request pada saat yang sama
        return call(base, "POST", f"/api/events/{event_id}/tickets", {"quantity": 1}, token)[0]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.requests) as pool:
        statuses = list(pool.map(purchase, tokens))
    elapsed = time.perf_counter() - started

    counts = Counter(statuses)
    _, body = call(base, "GET", f"/api/events/{event_id}")
    sold = body["event"]["sold"]
    print(f"[concurrency] {args.requests} request paralel selesai dalam {elapsed:.2f} detik")
    print(f"[concurrency] status HTTP: {dict(sorted(counts.items()))}")
    print(f"[concurrency] berhasil (201) = {counts.get(201, 0)}, ditolak (409) = {counts.get(409, 0)}, "
          f"sold di database = {sold}")

    if not args.keep_event:
        call(base, "DELETE", f"/api/events/{event_id}?force=true", token=admin)

    unexpected = {s: n for s, n in counts.items() if s not in (201, 409)}
    ok = counts.get(201, 0) == args.quota and sold == args.quota
    if sold > args.quota or counts.get(201, 0) > args.quota:
        print(f"[concurrency] GAGAL - OVERSELLING! terjual {max(sold, counts.get(201, 0))} > kuota {args.quota}")
        return 1
    if unexpected:
        print(f"[concurrency] GAGAL - ada respons tak terduga {unexpected} (cek log app: docker compose logs app)")
        return 1
    if not ok:
        print(f"[concurrency] GAGAL - tiket terjual {sold}, seharusnya tepat {args.quota}")
        return 1
    print(f"[concurrency] OK - tiket terjual tepat {args.quota}, tidak terjadi overselling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
