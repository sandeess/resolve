from enum import StrEnum


class DocumentKind(StrEnum):
    """What a document is for; decides who may upload it."""

    STYLESHEET = "stylesheet"
    GUIDELINE = "guideline"
    MANUSCRIPT = "manuscript"
    EMAIL_ATTACHMENT = "email_attachment"
    OTHER = "other"


#: Kinds that define journal rules and so need the stylesheet permission.
RULE_KINDS = frozenset({DocumentKind.STYLESHEET, DocumentKind.GUIDELINE})


class VersionStatus(StrEnum):
    """Ingestion state of a document version."""

    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class TicketStatus(StrEnum):
    """Lifecycle of a ticket.

    `resolved` has an answer awaiting a lead's approval; only `closed` tickets
    (approved) become searchable knowledge.
    """

    OPEN = "open"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TicketSource(StrEnum):
    WEB = "web"
    ASK_ESCALATION = "ask_escalation"
