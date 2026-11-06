"""Background job queue (Procrastinate, backed by the app's Postgres)."""

from procrastinate import App, PsycopgConnector

from app.core.config import settings

queue = App(
    connector=PsycopgConnector(conninfo=settings.queue_dsn),
    import_paths=["app.workers.tasks"],
)
