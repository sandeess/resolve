import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from pydantic import EmailStr
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Enum,
    Index,
    Integer,
    Sequence,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, SQLModel

from app.domain.enums import (
    DocumentKind,
    TicketPriority,
    TicketSource,
    TicketStatus,
    VersionStatus,
)
from app.domain.policy import Role

#: Dimension of stored embeddings; changing it needs a migration and re-index.
EMBEDDING_DIM = 1024


def utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp() -> Any:
    return Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True), nullable=False
    )


def _enum_column[E: StrEnum](enum_cls: type[E]) -> Column[Any]:
    """Stores an enum as a VARCHAR of its values (no native PG enum to migrate)."""
    return Column(
        Enum(
            enum_cls,
            native_enum=False,
            length=32,
            values_callable=lambda e: [member.value for member in e],
        ),
        nullable=False,
    )


# --- Users ------------------------------------------------------------------


class User(SQLModel, table=True):
    """A person known to the identity provider; created on first login."""

    __tablename__ = "app_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sub: str = Field(unique=True, index=True, max_length=255)
    email: EmailStr = Field(index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime = _timestamp()


class UserPublic(SQLModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_admin: bool


# --- Journals ---------------------------------------------------------------


class JournalBase(SQLModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=255)


class JournalCreate(JournalBase):
    pass


class Journal(JournalBase, table=True):
    code: str = Field(unique=True, index=True, min_length=2, max_length=32)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = _timestamp()


class JournalPublic(JournalBase):
    id: uuid.UUID
    role: Role | None = None


class JournalsPublic(SQLModel):
    data: list[JournalPublic]
    count: int


class JournalMember(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("journal_id", "user_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    journal_id: uuid.UUID = Field(
        foreign_key="journal.id", ondelete="CASCADE", index=True
    )
    user_id: uuid.UUID = Field(
        foreign_key="app_user.id", ondelete="CASCADE", index=True
    )
    role: Role = Field(sa_column=_enum_column(Role))


class MemberUpsert(SQLModel):
    email: EmailStr
    role: Role


class MemberPublic(SQLModel):
    user_id: uuid.UUID
    email: EmailStr
    role: Role


# --- Articles ---------------------------------------------------------------


class ArticleBase(SQLModel):
    manuscript_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)


class ArticleCreate(ArticleBase):
    pass


class Article(ArticleBase, table=True):
    __table_args__ = (UniqueConstraint("journal_id", "manuscript_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    journal_id: uuid.UUID = Field(
        foreign_key="journal.id", ondelete="CASCADE", index=True
    )
    created_at: datetime = _timestamp()


class ArticlePublic(ArticleBase):
    id: uuid.UUID
    journal_id: uuid.UUID


# --- Documents and versions -------------------------------------------------


class Document(SQLModel, table=True):
    """A logical file (e.g. "Style guide.docx") that accumulates versions.

    `article_id` is null for journal-level documents such as stylesheets.
    """

    __table_args__ = (
        Index(
            "uq_document_identity",
            "journal_id",
            text("coalesce(article_id, '00000000-0000-0000-0000-000000000000')"),
            "kind",
            "name",
            unique=True,
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    journal_id: uuid.UUID = Field(
        foreign_key="journal.id", ondelete="CASCADE", index=True
    )
    article_id: uuid.UUID | None = Field(
        default=None, foreign_key="article.id", ondelete="CASCADE", index=True
    )
    kind: DocumentKind = Field(sa_column=_enum_column(DocumentKind))
    name: str = Field(max_length=255)
    created_at: datetime = _timestamp()


class DocumentVersion(SQLModel, table=True):
    """One immutable revision of a document; exactly one is current."""

    __table_args__ = (
        UniqueConstraint("document_id", "version_no"),
        Index(
            "uq_document_current_version",
            "document_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(
        foreign_key="document.id", ondelete="CASCADE", index=True
    )
    version_no: int
    is_current: bool = True
    sha256: str = Field(max_length=64, index=True)
    size_bytes: int
    content_type: str = Field(max_length=255)
    storage_key: str = Field(max_length=512)
    status: VersionStatus = Field(
        default=VersionStatus.PENDING, sa_column=_enum_column(VersionStatus)
    )
    status_detail: str | None = Field(default=None, max_length=1000)
    uploaded_by: uuid.UUID = Field(foreign_key="app_user.id")
    created_at: datetime = _timestamp()


class DocumentVersionPublic(SQLModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_no: int
    is_current: bool
    sha256: str
    size_bytes: int
    content_type: str
    status: VersionStatus
    status_detail: str | None = None
    created_at: datetime


class DocumentPublic(SQLModel):
    id: uuid.UUID
    journal_id: uuid.UUID
    article_id: uuid.UUID | None
    kind: DocumentKind
    name: str
    current_version: DocumentVersionPublic | None = None


class DocumentsPublic(SQLModel):
    data: list[DocumentPublic]
    count: int


# --- Tickets ----------------------------------------------------------------


class TicketCreate(SQLModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=10_000)
    article_id: uuid.UUID | None = None
    priority: TicketPriority = TicketPriority.NORMAL
    source: TicketSource = TicketSource.WEB


class Ticket(SQLModel, table=True):
    __table_args__ = (Index("ix_ticket_journal_status", "journal_id", "status"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    number: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, Sequence("ticket_number_seq"), nullable=False, unique=True
        ),
    )
    journal_id: uuid.UUID = Field(
        foreign_key="journal.id", ondelete="CASCADE", index=True
    )
    article_id: uuid.UUID | None = Field(
        default=None, foreign_key="article.id", ondelete="CASCADE", index=True
    )
    title: str = Field(max_length=300)
    description: str = Field(default="", max_length=10_000)
    status: TicketStatus = Field(
        default=TicketStatus.OPEN, sa_column=_enum_column(TicketStatus)
    )
    priority: TicketPriority = Field(
        default=TicketPriority.NORMAL, sa_column=_enum_column(TicketPriority)
    )
    source: TicketSource = Field(
        default=TicketSource.WEB, sa_column=_enum_column(TicketSource)
    )
    created_by: uuid.UUID = Field(foreign_key="app_user.id")
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class TicketMessage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(
        foreign_key="ticket.id", ondelete="CASCADE", index=True
    )
    author_id: uuid.UUID = Field(foreign_key="app_user.id")
    body: str = Field(max_length=10_000)
    created_at: datetime = _timestamp()


class TicketResolution(SQLModel, table=True):
    """The reusable answer to a ticket. Becomes knowledge once approved."""

    ticket_id: uuid.UUID = Field(
        foreign_key="ticket.id", ondelete="CASCADE", primary_key=True
    )
    answer: str = Field(max_length=10_000)
    resolved_by: uuid.UUID = Field(foreign_key="app_user.id")
    approved_by: uuid.UUID | None = Field(default=None, foreign_key="app_user.id")
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = _timestamp()


class MessageCreate(SQLModel):
    body: str = Field(min_length=1, max_length=10_000)


class TicketUpdate(SQLModel):
    priority: TicketPriority | None = None
    # `assign_to_me` takes the ticket; `unassign` clears the assignee.
    assign_to_me: bool = False
    unassign: bool = False


class ResolveRequest(SQLModel):
    answer: str = Field(min_length=3, max_length=10_000)
    # Resolve and approve in one step; needs the approve permission.
    approve: bool = False


class MessagePublic(SQLModel):
    id: uuid.UUID
    author_email: str
    body: str
    created_at: datetime


class ResolutionPublic(SQLModel):
    answer: str
    resolved_by_email: str
    approved_by_email: str | None = None
    approved_at: datetime | None = None


class TicketPublic(SQLModel):
    id: uuid.UUID
    number: int
    journal_id: uuid.UUID
    article_id: uuid.UUID | None
    title: str
    status: TicketStatus
    priority: TicketPriority
    source: TicketSource
    created_by_email: str
    assignee_email: str | None = None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketPublic):
    description: str
    messages: list[MessagePublic]
    resolution: ResolutionPublic | None = None


class TicketsPublic(SQLModel):
    data: list[TicketPublic]
    count: int


# --- Chunks -----------------------------------------------------------------


class Chunk(SQLModel, table=True):
    """A passage of a document version or approved ticket, embedded for retrieval.

    Document chunks are "current" exactly when their version is, so there is no
    flag to keep in sync on revision. Ticket chunks exist only while the ticket
    is closed (approved): reopening a ticket deletes them.
    """

    __table_args__ = (
        Index(
            "ix_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        UniqueConstraint("version_id", "chunk_index"),
        UniqueConstraint("ticket_id", "chunk_index"),
        CheckConstraint(
            "(version_id IS NULL) <> (ticket_id IS NULL)", name="ck_chunk_one_source"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Exactly one of version_id / ticket_id is set.
    version_id: uuid.UUID | None = Field(
        default=None, foreign_key="documentversion.id", ondelete="CASCADE", index=True
    )
    ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="ticket.id", ondelete="CASCADE", index=True
    )
    # Denormalised from the document so scope filters need no join.
    journal_id: uuid.UUID = Field(
        foreign_key="journal.id", ondelete="CASCADE", index=True
    )
    article_id: uuid.UUID | None = Field(
        default=None, foreign_key="article.id", ondelete="CASCADE", index=True
    )
    chunk_index: int
    content: str
    locator: str = Field(default="", max_length=255)
    embedding: list[float] = Field(
        sa_column=Column(Vector(EMBEDDING_DIM), nullable=False)
    )
    embedding_model: str = Field(max_length=128)
    tsv: Any = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed("to_tsvector('english', content)", persisted=True),
        ),
    )


class AskRequest(SQLModel):
    question: str = Field(min_length=3, max_length=2000)
    article_id: uuid.UUID | None = None


# --- Generic ----------------------------------------------------------------


class Message(SQLModel):
    message: str
