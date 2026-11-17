#!/usr/bin/env bash
# Creates .env from .env.example with freshly generated random secrets. Owner: Amina A.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists - not touching it."; exit 0; fi
rand() { python3 -c "import secrets; print(secrets.token_urlsafe(${1:-32}))"; }
sed -e "s|change-me-django-secret|$(rand 50)|" -e "s|change-me-db-password|$(rand 24)|" .env.example > .env
chmod 600 .env
echo "Created .env with random secrets (it is git-ignored)."
