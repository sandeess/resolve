#!/usr/bin/env bash
# One-command update on the server: pull the latest code, rebuild, restart, show status.
#
#   cd /opt/resolve && sudo bash deploy/update.sh
#
# Database migrations run automatically (the `prestart` step) and are safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="${COMPOSE:-docker compose --env-file .env.prod -f compose.prod.yml}"

git pull --ff-only
$COMPOSE up -d --build
echo
$COMPOSE ps
echo
echo "Health: $($COMPOSE exec -T backend curl -fsS http://localhost:8000/api/v1/utils/health-check/ || echo 'NOT HEALTHY')"
