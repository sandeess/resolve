import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, EmbedderDep, ScopeDep, SessionDep
from app.domain.enums import TicketStatus
from app.llm.base import LlmError
from app.models import (
    MessageCreate,
    ResolveRequest,
    TicketCreate,
    TicketDetail,
    TicketsPublic,
    TicketUpdate,
)
from app.services import tickets

router = APIRouter(tags=["tickets"])


@router.post(
    "/journals/{journal_id}/tickets",
    response_model=TicketDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    session: SessionDep,
    scope: ScopeDep,
    user: CurrentUser,
    journal_id: uuid.UUID,
    body: TicketCreate,
) -> TicketDetail:
    """Raises a ticket. Anyone who can ask in the journal can raise one."""
    ticket = tickets.create_ticket(session, scope, user, journal_id, body)
    return tickets.get_ticket(session, scope, ticket.id)


@router.get("/journals/{journal_id}/tickets", response_model=TicketsPublic)
def list_tickets(
    session: SessionDep,
    scope: ScopeDep,
    journal_id: uuid.UUID,
    status: TicketStatus | None = None,
    article_id: uuid.UUID | None = None,
) -> TicketsPublic:
    data = tickets.list_tickets(
        session, scope, journal_id, status=status, article_id=article_id
    )
    return TicketsPublic(data=data, count=len(data))


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def read_ticket(
    session: SessionDep, scope: ScopeDep, ticket_id: uuid.UUID
) -> TicketDetail:
    return tickets.get_ticket(session, scope, ticket_id)


@router.post("/tickets/{ticket_id}/messages", response_model=TicketDetail)
def add_message(
    session: SessionDep,
    scope: ScopeDep,
    user: CurrentUser,
    ticket_id: uuid.UUID,
    body: MessageCreate,
) -> TicketDetail:
    tickets.add_message(session, scope, user, ticket_id, body.body)
    return tickets.get_ticket(session, scope, ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=TicketDetail)
def update_ticket(
    session: SessionDep,
    scope: ScopeDep,
    user: CurrentUser,
    ticket_id: uuid.UUID,
    body: TicketUpdate,
) -> TicketDetail:
    tickets.update_ticket(session, scope, user, ticket_id, body)
    return tickets.get_ticket(session, scope, ticket_id)


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketDetail)
def resolve_ticket(
    session: SessionDep,
    scope: ScopeDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    ticket_id: uuid.UUID,
    body: ResolveRequest,
) -> TicketDetail:
    """Records the answer. With `approve`, a lead also publishes it to search."""
    try:
        tickets.resolve_ticket(
            session,
            scope,
            user,
            embedder,
            ticket_id,
            answer=body.answer,
            approve=body.approve,
        )
    except LlmError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return tickets.get_ticket(session, scope, ticket_id)


@router.post("/tickets/{ticket_id}/approve", response_model=TicketDetail)
def approve_ticket(
    session: SessionDep,
    scope: ScopeDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    ticket_id: uuid.UUID,
) -> TicketDetail:
    """A lead approves the answer: the ticket closes and becomes searchable."""
    try:
        tickets.approve_ticket(session, scope, user, embedder, ticket_id)
    except LlmError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return tickets.get_ticket(session, scope, ticket_id)


@router.post("/tickets/{ticket_id}/reopen", response_model=TicketDetail)
def reopen_ticket(
    session: SessionDep, scope: ScopeDep, ticket_id: uuid.UUID
) -> TicketDetail:
    """Reopens the ticket and withdraws its answer from search."""
    tickets.reopen_ticket(session, scope, ticket_id)
    return tickets.get_ticket(session, scope, ticket_id)
