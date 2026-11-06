#! /usr/bin/env bash

set -e
set -x

# Run migrations
alembic upgrade head

# Create the job-queue tables (idempotent)
procrastinate --app=app.workers.queue.queue schema --apply
