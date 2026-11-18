#!/bin/sh
# Production start (Render).   Owner: Aitore
# 1) apply migrations  2) load demo data once (SEED_DEMO=1, skipped if data exists)  3) start gunicorn on $PORT
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo || echo "seed_demo skipped: data already present"
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-2}" --threads 4 --timeout 60 --access-logfile - --error-logfile -
