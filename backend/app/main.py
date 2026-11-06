from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import hide_query_strings_in_access_logs
from app.domain.errors import DomainError
from app.workers.queue import queue

FRONTEND_DIR = Path(__file__).parent / "frontend"

hide_query_strings_in_access_logs()


def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "app"
    return f"{tag}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # The API only enqueues jobs; a separate worker process runs them.
    # Sync open: psycopg's async pool cannot run on Windows' default event loop.
    with queue.open():
        yield


# Interactive API docs and the schema are for developers: not published in production.
_DEV = settings.FASTAPI_ENV == "development"

app = FastAPI(
    lifespan=lifespan,
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if _DEV else None,
    docs_url="/docs" if _DEV else None,
    redoc_url="/redoc" if _DEV else None,
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.api_route(
    f"{settings.API_V1_STR}/{{path:path}}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def api_not_found(path: str) -> None:  # noqa: ARG001
    """Unknown API paths answer JSON 404, never the web app's index page."""
    raise HTTPException(status_code=404, detail="Not Found")


# The SPA bundle only exists in built images; in dev the Vite server serves it.
# Direct visits to client-side routes get index.html (the default fallback).
if FRONTEND_DIR.is_dir():
    app.frontend("/", directory=FRONTEND_DIR)
