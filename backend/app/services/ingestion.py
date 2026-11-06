"""Index a document version: parse -> chunk -> embed -> store."""

import logging
import uuid

from sqlalchemy import delete
from sqlmodel import Session, col

from app.domain.enums import VersionStatus
from app.domain.errors import NotFoundError
from app.ingestion.chunker import chunk_sections
from app.ingestion.parsers import ParseError, parse
from app.llm.base import Embedder
from app.models import Chunk, Document, DocumentVersion
from app.storage.base import Storage

logger = logging.getLogger(__name__)


def embedding_text(document_name: str, locator: str, content: str) -> str:
    """Text that gets embedded: the passage prefixed with where it lives.

    The prefix lets a query such as "date format in the style guide" match a
    passage that never repeats the document or section name.
    """
    return f"{document_name} - {locator}\n{content}"


def ingest_version(
    session: Session, storage: Storage, embedder: Embedder, version_id: uuid.UUID
) -> int:
    """Indexes one version and returns the number of chunks written.

    Safe to re-run: existing chunks for the version are replaced. Unreadable
    files are marked failed (retrying cannot help); other errors, such as a
    gateway outage, mark the version failed and propagate so callers can see
    them; a re-index request retries.
    """
    version = session.get(DocumentVersion, version_id)
    if version is None:
        raise NotFoundError("version not found")
    document = session.get(Document, version.document_id)
    if document is None:
        raise NotFoundError("document not found")

    try:
        sections = parse(
            filename=document.name,
            content_type=version.content_type,
            data=storage.get(version.storage_key),
        )
        pieces = chunk_sections(sections)
        vectors = embedder.embed(
            [embedding_text(document.name, p.locator, p.text) for p in pieces]
        )
    except ParseError as exc:
        _set_status(session, version, VersionStatus.FAILED, str(exc))
        return 0
    except Exception as exc:
        _set_status(session, version, VersionStatus.FAILED, f"indexing error: {exc}")
        raise

    session.execute(delete(Chunk).where(col(Chunk.version_id) == version.id))
    session.add_all(
        Chunk(
            version_id=version.id,
            journal_id=document.journal_id,
            article_id=document.article_id,
            chunk_index=index,
            content=piece.text,
            locator=piece.locator,
            embedding=vector,
            embedding_model=embedder.model_name,
        )
        for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
    )
    _set_status(session, version, VersionStatus.INDEXED, None)
    logger.info("indexed version %s: %d chunks", version.id, len(pieces))
    return len(pieces)


def _set_status(
    session: Session,
    version: DocumentVersion,
    status: VersionStatus,
    detail: str | None,
) -> None:
    version.status = status
    version.status_detail = detail[:1000] if detail else None
    session.add(version)
    session.commit()
