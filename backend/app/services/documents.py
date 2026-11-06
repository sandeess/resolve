"""Versioned document storage.

Re-uploading a document under the same identity creates a new immutable
version; the previous one stays for audit but stops being current. Retrieval
only ever looks at current versions.
"""

import hashlib
import uuid

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.enums import RULE_KINDS, DocumentKind, VersionStatus
from app.domain.errors import ConflictError, NotFoundError, PayloadTooLargeError
from app.domain.policy import Action, Scope
from app.models import (
    Article,
    Document,
    DocumentPublic,
    DocumentVersion,
    DocumentVersionPublic,
    User,
)
from app.services.access import require
from app.storage.base import Storage


def upload_action(kind: DocumentKind) -> Action:
    """Returns the permission needed to upload a document of `kind`."""
    return Action.UPLOAD_STYLESHEET if kind in RULE_KINDS else Action.UPLOAD_CONTENT


def upload_version(
    session: Session,
    storage: Storage,
    scope: Scope,
    user: User,
    *,
    journal_id: uuid.UUID,
    article_id: uuid.UUID | None,
    kind: DocumentKind,
    name: str,
    content_type: str,
    data: bytes,
    max_bytes: int,
) -> DocumentVersion:
    """Stores `data` as the newest version of the identified document.

    Uploading bytes identical to the current version is a no-op and returns it.

    Raises:
        PermissionDeniedError: The caller may not upload this kind here.
        NotFoundError: The article does not belong to the journal.
        PayloadTooLargeError: `data` exceeds `max_bytes`.
        ConflictError: A concurrent upload created the same document first.
    """
    require(scope, journal_id, upload_action(kind))
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"file exceeds {max_bytes // (1024 * 1024)} MB")
    if article_id is not None:
        article = session.get(Article, article_id)
        if article is None or article.journal_id != journal_id:
            raise NotFoundError("article not found in this journal")

    document = _get_or_create_document(
        session, journal_id=journal_id, article_id=article_id, kind=kind, name=name
    )
    current = session.exec(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id, col(DocumentVersion.is_current)
        )
    ).first()
    sha256 = hashlib.sha256(data).hexdigest()
    if current is not None and current.sha256 == sha256:
        return current

    latest = session.exec(
        select(func.max(DocumentVersion.version_no)).where(
            DocumentVersion.document_id == document.id
        )
    ).one()
    version_no = (latest or 0) + 1
    key = f"journal/{journal_id}/doc/{document.id}/v{version_no}/{sha256}"
    storage.put(key, data)

    if current is not None:
        current.is_current = False
        session.add(current)
        session.flush()  # release the "one current version" unique index first
    version = DocumentVersion(
        document_id=document.id,
        version_no=version_no,
        sha256=sha256,
        size_bytes=len(data),
        content_type=content_type,
        storage_key=key,
        uploaded_by=user.id,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def _get_or_create_document(
    session: Session,
    *,
    journal_id: uuid.UUID,
    article_id: uuid.UUID | None,
    kind: DocumentKind,
    name: str,
) -> Document:
    scope_filter = (
        Document.article_id == article_id
        if article_id is not None
        else col(Document.article_id).is_(None)
    )
    document = session.exec(
        select(Document)
        .where(
            Document.journal_id == journal_id,
            scope_filter,
            Document.kind == kind,
            Document.name == name,
        )
        .with_for_update()
    ).first()
    if document is not None:
        return document
    document = Document(
        journal_id=journal_id, article_id=article_id, kind=kind, name=name
    )
    session.add(document)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("document was created concurrently; retry") from exc
    return document


def list_documents(
    session: Session,
    scope: Scope,
    journal_id: uuid.UUID,
    *,
    article_id: uuid.UUID | None = None,
) -> list[DocumentPublic]:
    """Lists documents with their current version (journal-level if no article)."""
    require(scope, journal_id, Action.READ)
    scope_filter = (
        Document.article_id == article_id
        if article_id is not None
        else col(Document.article_id).is_(None)
    )
    rows = session.exec(
        select(Document, DocumentVersion)
        .join(
            DocumentVersion,
            (col(DocumentVersion.document_id) == col(Document.id))
            & col(DocumentVersion.is_current),
            isouter=True,
        )
        .where(Document.journal_id == journal_id, scope_filter)
        .order_by(col(Document.name))
    ).all()
    return [
        DocumentPublic(
            id=doc.id,
            journal_id=doc.journal_id,
            article_id=doc.article_id,
            kind=doc.kind,
            name=doc.name,
            current_version=(
                DocumentVersionPublic.model_validate(ver) if ver else None
            ),
        )
        for doc, ver in rows
    ]


def list_versions(
    session: Session, scope: Scope, document_id: uuid.UUID
) -> list[DocumentVersion]:
    """Returns every version of a document, newest first."""
    document = _get_document(session, scope, document_id)
    return list(
        session.exec(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(col(DocumentVersion.version_no).desc())
        )
    )


def read_version(
    session: Session, storage: Storage, scope: Scope, version_id: uuid.UUID
) -> tuple[Document, DocumentVersion, bytes]:
    """Loads a version's bytes after checking read access."""
    version = session.get(DocumentVersion, version_id)
    if version is None:
        raise NotFoundError("version not found")
    document = _get_document(session, scope, version.document_id)
    return document, version, storage.get(version.storage_key)


def _get_document(session: Session, scope: Scope, document_id: uuid.UUID) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise NotFoundError("document not found")
    require(scope, document.journal_id, Action.READ)
    return document


def prepare_reindex(
    session: Session, scope: Scope, version_id: uuid.UUID
) -> DocumentVersion:
    """Resets a version to pending after checking the caller may upload it."""
    version = session.get(DocumentVersion, version_id)
    if version is None:
        raise NotFoundError("version not found")
    document = session.get(Document, version.document_id)
    if document is None:
        raise NotFoundError("document not found")
    require(scope, document.journal_id, upload_action(document.kind))
    version.status = VersionStatus.PENDING
    version.status_detail = None
    session.add(version)
    session.commit()
    session.refresh(version)
    return version
