#!/bin/sh
# Owner: Amina A. - prepares the database, then starts the server.
set -e
# Dev convenience: creates the migration files the first time (commit them afterwards!).
python manage.py makemigrations accounts catalog bookings --noinput
python manage.py migrate --noinput
if [ "$SEED_DEMO" = "1" ]; then
  python manage.py seed_demo || echo "seed_demo skipped (data already present)"
fi
exec "$@"
