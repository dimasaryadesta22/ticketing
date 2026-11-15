#!/bin/sh
# Entrypoint container app: jalankan migrasi + seeder, lalu start gunicorn.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate
fi

if [ "${RUN_SEED:-true}" = "true" ]; then
  python manage.py seed
fi

exec "$@"
