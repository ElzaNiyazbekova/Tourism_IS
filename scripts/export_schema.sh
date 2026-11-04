#!/usr/bin/env bash
# Exports the real schema of the running database to db/schema.sql.  Owner: Elza
# Docker:  docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only --no-owner --no-privileges > db/schema.sql
# Local:   PGPASSWORD=... pg_dump -h localhost -U tourism -d tourism --schema-only --no-owner --no-privileges > db/schema.sql
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only --no-owner --no-privileges > db/schema.sql
echo "Wrote db/schema.sql ($(wc -l < db/schema.sql) lines)"
