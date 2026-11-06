import uuid

import pytest
from sqlmodel import Session, col, select

from app.domain.enums import DocumentKind
from app.domain.errors import NotFoundError, PayloadTooLargeError, PermissionDeniedError
from app.domain.policy import Role
from app.models import Article, DocumentVersion, Journal, User
from app.services import access, documents
from app.storage.local import LocalStorage
from tests.integration.conftest import add_member, make_journal, make_user

MAX = 1024


def _upload(
    session: Session,
    storage: LocalStorage,
    user: User,
    journal: Journal,
    data: bytes,
    *,
    kind: DocumentKind = DocumentKind.STYLESHEET,
    name: str = "style.docx",
    article_id: uuid.UUID | None = None,
    max_bytes: int = MAX,
) -> DocumentVersion:
    return documents.upload_version(
        session,
        storage,
        access.build_scope(session, user),
        user,
        journal_id=journal.id,
        article_id=article_id,
        kind=kind,
        name=name,
        content_type="application/octet-stream",
        data=data,
        max_bytes=max_bytes,
    )


def _lead_in_new_journal(session: Session, code: str = "JA") -> tuple[User, Journal]:
    lead, journal = make_user(session, "lead"), make_journal(session, code)
    add_member(session, journal, lead, Role.LEAD)
    return lead, journal


def test_revision_supersedes_previous_version(
    session: Session, storage: LocalStorage
) -> None:
    lead, journal = _lead_in_new_journal(session)

    v1 = _upload(session, storage, lead, journal, b"rules v1")
    v2 = _upload(session, storage, lead, journal, b"rules v2")

    versions = session.exec(
        select(DocumentVersion).order_by(col(DocumentVersion.version_no))
    ).all()
    assert [(v.version_no, v.is_current) for v in versions] == [(1, False), (2, True)]
    assert storage.get(v1.storage_key) == b"rules v1"  # old bytes kept for audit
    assert storage.get(v2.storage_key) == b"rules v2"


def test_identical_reupload_is_a_noop(session: Session, storage: LocalStorage) -> None:
    lead, journal = _lead_in_new_journal(session)

    first = _upload(session, storage, lead, journal, b"same")
    again = _upload(session, storage, lead, journal, b"same")

    assert again.id == first.id
    assert len(session.exec(select(DocumentVersion)).all()) == 1


def test_same_name_in_different_scopes_is_separate(
    session: Session, storage: LocalStorage
) -> None:
    lead, journal = _lead_in_new_journal(session)
    article = Article(journal_id=journal.id, manuscript_id="M1", title="Paper")
    session.add(article)
    session.commit()

    kind = DocumentKind.OTHER
    at_journal = _upload(session, storage, lead, journal, b"a", kind=kind)
    at_article = _upload(
        session, storage, lead, journal, b"a", kind=kind, article_id=article.id
    )
    assert at_journal.document_id != at_article.document_id


@pytest.mark.parametrize(
    ("role", "kind", "allowed"),
    [
        (Role.LEAD, DocumentKind.STYLESHEET, True),
        (Role.ASSISTANT, DocumentKind.STYLESHEET, False),
        (Role.ASSISTANT, DocumentKind.MANUSCRIPT, True),
        (Role.VIEWER, DocumentKind.MANUSCRIPT, False),
    ],
)
def test_upload_permissions(
    session: Session,
    storage: LocalStorage,
    role: Role,
    kind: DocumentKind,
    allowed: bool,
) -> None:
    user, journal = make_user(session, "u"), make_journal(session, "JA")
    add_member(session, journal, user, role)
    if allowed:
        _upload(session, storage, user, journal, b"x", kind=kind)
    else:
        with pytest.raises(PermissionDeniedError):
            _upload(session, storage, user, journal, b"x", kind=kind)


def test_non_member_cannot_upload(session: Session, storage: LocalStorage) -> None:
    outsider, journal = make_user(session, "out"), make_journal(session, "JA")
    with pytest.raises(PermissionDeniedError):
        _upload(session, storage, outsider, journal, b"x", kind=DocumentKind.OTHER)


def test_article_must_belong_to_journal(
    session: Session, storage: LocalStorage
) -> None:
    lead, ja = _lead_in_new_journal(session, "JA")
    jb = make_journal(session, "JB")
    article_b = Article(journal_id=jb.id, manuscript_id="M1", title="Other")
    session.add(article_b)
    session.commit()

    for article_id in (article_b.id, uuid.uuid4()):
        with pytest.raises(NotFoundError):
            _upload(
                session,
                storage,
                lead,
                ja,
                b"x",
                kind=DocumentKind.OTHER,
                article_id=article_id,
            )


def test_oversize_rejected(session: Session, storage: LocalStorage) -> None:
    lead, journal = _lead_in_new_journal(session)
    with pytest.raises(PayloadTooLargeError):
        _upload(session, storage, lead, journal, b"x" * (MAX + 1))
