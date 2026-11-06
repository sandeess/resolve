import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from app.api.deps import CurrentUser, ScopeDep, SessionDep, StorageDep
from app.core.config import settings
from app.domain.enums import DocumentKind, VersionStatus
from app.ingestion.parsers import is_supported
from app.models import (
    DocumentsPublic,
    DocumentVersion,
    DocumentVersionPublic,
)
from app.services import documents
from app.workers.tasks import ingest_document_version

router = APIRouter(tags=["documents"])


@router.post(
    "/journals/{journal_id}/documents",
    response_model=DocumentVersionPublic,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    session: SessionDep,
    storage: StorageDep,
    scope: ScopeDep,
    user: CurrentUser,
    journal_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    kind: Annotated[DocumentKind, Form()],
    article_id: Annotated[uuid.UUID | None, Form()] = None,
) -> DocumentVersion:
    """Uploads a file as the newest version of the document with that name.

    The whole body is read up to the size limit plus one byte, so oversized
    uploads are rejected without buffering them entirely.
    """
    name = file.filename or "untitled"
    content_type = file.content_type or "application/octet-stream"
    if not is_supported(name, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a PDF, Word (.docx), Markdown, text or email (.eml) file.",
        )
    data = file.file.read(settings.max_upload_bytes + 1)
    version = documents.upload_version(
        session,
        storage,
        scope,
        user,
        journal_id=journal_id,
        article_id=article_id,
        kind=kind,
        name=name,
        content_type=content_type,
        data=data,
        max_bytes=settings.max_upload_bytes,
    )
    if version.status == VersionStatus.PENDING:
        ingest_document_version.defer(version_id=str(version.id))
    return version


@router.post(
    "/document-versions/{version_id}/reindex",
    response_model=DocumentVersionPublic,
    status_code=status.HTTP_202_ACCEPTED,
)
def reindex_version(
    session: SessionDep, scope: ScopeDep, version_id: uuid.UUID
) -> DocumentVersion:
    """Queues indexing again, e.g. after a failure (needs upload permission)."""
    version = documents.prepare_reindex(session, scope, version_id)
    ingest_document_version.defer(version_id=str(version.id))
    return version


@router.get("/journals/{journal_id}/documents", response_model=DocumentsPublic)
def list_documents(
    session: SessionDep,
    scope: ScopeDep,
    journal_id: uuid.UUID,
    article_id: uuid.UUID | None = None,
) -> DocumentsPublic:
    """Lists documents at journal level, or under one article if given."""
    data = documents.list_documents(session, scope, journal_id, article_id=article_id)
    return DocumentsPublic(data=data, count=len(data))


@router.get(
    "/documents/{document_id}/versions", response_model=list[DocumentVersionPublic]
)
def list_versions(
    session: SessionDep, scope: ScopeDep, document_id: uuid.UUID
) -> list[DocumentVersion]:
    return documents.list_versions(session, scope, document_id)


@router.get("/document-versions/{version_id}/download")
def download_version(
    session: SessionDep, storage: StorageDep, scope: ScopeDep, version_id: uuid.UUID
) -> Response:
    """Streams the original bytes of one version (access-checked)."""
    document, version, data = documents.read_version(
        session, storage, scope, version_id
    )
    filename = quote(document.name)
    return Response(
        content=data,
        media_type=version.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
