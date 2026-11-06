#! /usr/bin/env bash

set -e
set -x

# Run migrations
alembic upgrade head

# Create the job-queue tables, only if they are not there yet: `schema --apply` fails
# on a database that already has them, so a plain re-run (every deploy) would break.
if python - <<'PY'
import sys

import psycopg

from app.core.config import settings

with psycopg.connect(settings.queue_dsn) as conn:
    present = conn.execute("select to_regclass('public.procrastinate_jobs')").fetchone()[0]
sys.exit(0 if present else 1)
PY
then
  echo "Job-queue tables already exist; leaving them as they are."
else
  procrastinate --app=app.workers.queue.queue schema --apply
fi
