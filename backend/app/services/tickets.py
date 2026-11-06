"""Tickets: raise, work, resolve, approve.

A ticket's answer only becomes searchable knowledge once a lead approves it
(status `closed`). Reopening withdraws it again, so retrieval never serves an
answer a lead has not vouched for or that was found wrong.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.domain.enums import TicketStatus
from app.domain.errors import ConflictError, DomainError, NotFoundError
from app.domain.policy import Action, Scope
from app.ingestion.chunker import chunk_sections
from app.ingestion.parsers import Section
from app.llm.base import Embedder
from app.models import (
    Article,
    Chunk,
    MessagePublic,
    ResolutionPublic,
    Ticket,
    TicketCreate,
    TicketDetail,
    TicketMessage,
    TicketPublic,
    TicketResolution,
    TicketUpdate,
    User,
    utc_now,
)
from app.services.access import require
from app.services.ingestion import embedding_text


def ticket_label(number: int) -> str:
    return f"T-{number}"


def create_ticket(
    session: Session,
    scope: Scope,
    user: User,
    journal_id: uuid.UUID,
    data: TicketCreate,
) -> Ticket:
    """Raises a ticket in a journal. Anyone who can ask can raise one."""
    require(scope, journal_id, Action.CREATE_TICKET)
    if data.article_id is not None:
        article = session.get(Article, data.article_id)
        if article is None or article.journal_id != journal_id:
            raise NotFoundError("article not found in this journal")
    ticket = Ticket(
        journal_id=journal_id,
        article_id=data.article_id,
        title=data.title.strip(),
        description=data.description.strip(),
        priority=data.priority,
        source=data.source,
        created_by=user.id,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def list_tickets(
    session: Session,
    scope: Scope,
    journal_id: uuid.UUID,
    *,
    status: TicketStatus | None = None,
    article_id: uuid.UUID | None = None,
) -> list[TicketPublic]:
    require(scope, journal_id, Action.READ)
    query = select(Ticket).where(Ticket.journal_id == journal_id)
    if status is not None:
        query = query.where(Ticket.status == status)
    if article_id is not None:
        query = query.where(Ticket.article_id == article_id)
    tickets = session.exec(query.order_by(col(Ticket.number).desc())).all()
    emails = _emails(session, tickets)
    return [_public(t, emails) for t in tickets]


def get_ticket(session: Session, scope: Scope, ticket_id: uuid.UUID) -> TicketDetail:
    ticket = _load(session, scope, ticket_id, Action.READ)
    messages = session.exec(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket.id)
        .order_by(col(TicketMessage.created_at))
    ).all()
    resolution = session.get(TicketResolution, ticket.id)
    user_ids = {m.author_id for m in messages}
    if resolution:
        user_ids |= {resolution.resolved_by}
        if resolution.approved_by:
            user_ids.add(resolution.approved_by)
    emails = _emails(session, [ticket], extra=user_ids)
    return TicketDetail(
        **_public(ticket, emails).model_dump(),
        description=ticket.description,
        messages=[
            MessagePublic(
                id=m.id,
                author_email=emails[m.author_id],
                body=m.body,
                created_at=m.created_at,
            )
            for m in messages
        ],
        resolution=(
            ResolutionPublic(
                answer=resolution.answer,
                resolved_by_email=emails[resolution.resolved_by],
                approved_by_email=(
                    emails[resolution.approved_by] if resolution.approved_by else None
                ),
                approved_at=resolution.approved_at,
            )
            if resolution
            else None
        ),
    )


def add_message(
    session: Session, scope: Scope, user: User, ticket_id: uuid.UUID, body: str
) -> Ticket:
    """Adds a comment. The ticket's author and the team may comment."""
    ticket = _load(session, scope, ticket_id, Action.READ)
    is_team = scope.allows(ticket.journal_id, Action.WORK_TICKETS)
    if not is_team and ticket.created_by != user.id:
        require(scope, ticket.journal_id, Action.WORK_TICKETS)  # raises
    session.add(
        TicketMessage(ticket_id=ticket.id, author_id=user.id, body=body.strip())
    )
    _touch(session, ticket)
    session.commit()
    return ticket


def update_ticket(
    session: Session,
    scope: Scope,
    user: User,
    ticket_id: uuid.UUID,
    data: TicketUpdate,
) -> Ticket:
    ticket = _load(session, scope, ticket_id, Action.WORK_TICKETS)
    if data.assign_to_me and data.unassign:
        raise DomainError("choose either assign_to_me or unassign")
    if data.priority is not None:
        ticket.priority = data.priority
    if data.assign_to_me:
        ticket.assignee_id = user.id
    if data.unassign:
        ticket.assignee_id = None
    _touch(session, ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def resolve_ticket(
    session: Session,
    scope: Scope,
    user: User,
    embedder: Embedder,
    ticket_id: uuid.UUID,
    *,
    answer: str,
    approve: bool,
) -> Ticket:
    """Records the answer; with `approve`, also closes it into the knowledge base.

    Raises:
        PermissionDeniedError: `approve` without the approve permission.
        ConflictError: The ticket is closed (reopen it first).
    """
    ticket = _load(session, scope, ticket_id, Action.WORK_TICKETS)
    if approve:
        require(scope, ticket.journal_id, Action.APPROVE_RESOLUTION)
    if ticket.status == TicketStatus.CLOSED:
        raise ConflictError("ticket is closed; reopen it before changing the answer")

    answer = answer.strip()
    # Embed before changing anything: a gateway failure must leave no trace.
    chunks = _build_chunks(embedder, ticket, answer) if approve else []

    resolution = session.get(TicketResolution, ticket.id)
    if resolution is None:
        resolution = TicketResolution(
            ticket_id=ticket.id, answer=answer, resolved_by=user.id
        )
    else:
        resolution.answer = answer
        resolution.resolved_by = user.id
        resolution.approved_by = None
        resolution.approved_at = None
    ticket.status = TicketStatus.RESOLVED
    session.add(resolution)
    if approve:
        _stage_publish(session, ticket, resolution, chunks, approver=user)
    _touch(session, ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def approve_ticket(
    session: Session,
    scope: Scope,
    user: User,
    embedder: Embedder,
    ticket_id: uuid.UUID,
) -> Ticket:
    """A lead vouches for the answer; it becomes searchable knowledge."""
    ticket = _load(session, scope, ticket_id, Action.APPROVE_RESOLUTION)
    resolution = session.get(TicketResolution, ticket.id)
    if ticket.status != TicketStatus.RESOLVED or resolution is None:
        raise ConflictError("only a resolved ticket can be approved")
    chunks = _build_chunks(embedder, ticket, resolution.answer)
    _stage_publish(session, ticket, resolution, chunks, approver=user)
    _touch(session, ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def reopen_ticket(session: Session, scope: Scope, ticket_id: uuid.UUID) -> Ticket:
    """Reopens a ticket and withdraws its answer from search."""
    ticket = _load(session, scope, ticket_id, Action.WORK_TICKETS)
    if ticket.status == TicketStatus.OPEN:
        raise ConflictError("ticket is already open")
    session.execute(delete(Chunk).where(col(Chunk.ticket_id) == ticket.id))
    resolution = session.get(TicketResolution, ticket.id)
    if resolution is not None:
        resolution.approved_by = None
        resolution.approved_at = None
        session.add(resolution)
    ticket.status = TicketStatus.OPEN
    _touch(session, ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


# --- helpers ----------------------------------------------------------------


def _build_chunks(embedder: Embedder, ticket: Ticket, answer: str) -> list[Chunk]:
    """Embeds the ticket's question and answer. Touches no database state."""
    assert ticket.number is not None
    parts = [f"Question: {ticket.title}"]
    if ticket.description:
        parts.append(ticket.description)
    parts.append(f"Answer: {answer}")
    text = "\n\n".join(parts)
    pieces = chunk_sections([Section(text, ticket.title)])
    label = ticket_label(ticket.number)
    vectors = embedder.embed([embedding_text(label, p.locator, p.text) for p in pieces])
    return [
        Chunk(
            ticket_id=ticket.id,
            journal_id=ticket.journal_id,
            article_id=ticket.article_id,
            chunk_index=index,
            content=piece.text,
            locator=piece.locator,
            embedding=vector,
            embedding_model=embedder.model_name,
        )
        for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
    ]


def _stage_publish(
    session: Session,
    ticket: Ticket,
    resolution: TicketResolution,
    chunks: list[Chunk],
    *,
    approver: User,
) -> None:
    """Stages the knowledge chunks and approval; the caller commits."""
    session.execute(delete(Chunk).where(col(Chunk.ticket_id) == ticket.id))
    session.add_all(chunks)
    resolution.approved_by = approver.id
    resolution.approved_at = datetime.now(UTC)
    session.add(resolution)
    ticket.status = TicketStatus.CLOSED


def _touch(session: Session, ticket: Ticket) -> None:
    ticket.updated_at = utc_now()
    session.add(ticket)


def _load(
    session: Session, scope: Scope, ticket_id: uuid.UUID, action: Action
) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("ticket not found")
    require(scope, ticket.journal_id, action)
    return ticket


def _emails(
    session: Session,
    tickets: Sequence[Ticket],
    *,
    extra: set[uuid.UUID] | None = None,
) -> dict[uuid.UUID, str]:
    ids = set(extra or ())
    for t in tickets:
        ids.add(t.created_by)
        if t.assignee_id:
            ids.add(t.assignee_id)
    if not ids:
        return {}
    users = session.exec(select(User).where(col(User.id).in_(ids))).all()
    return {u.id: u.email for u in users}


def _public(ticket: Ticket, emails: dict[uuid.UUID, str]) -> TicketPublic:
    assert ticket.number is not None
    return TicketPublic(
        id=ticket.id,
        number=ticket.number,
        journal_id=ticket.journal_id,
        article_id=ticket.article_id,
        title=ticket.title,
        status=ticket.status,
        priority=ticket.priority,
        source=ticket.source,
        created_by_email=emails[ticket.created_by],
        assignee_email=emails[ticket.assignee_id] if ticket.assignee_id else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )
