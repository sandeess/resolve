import uuid

from sqlmodel import Session

from app.core.db import engine
from app.core.providers import get_embedder, get_storage
from app.services import ingestion
from app.workers.queue import queue


@queue.task(name="ingest_document_version", queue="ingestion")
def ingest_document_version(version_id: str) -> None:
    """Indexes a document version; enqueued after every upload."""
    with Session(engine) as session:
        ingestion.ingest_version(
            session, get_storage(), get_embedder(), uuid.UUID(version_id)
        )
