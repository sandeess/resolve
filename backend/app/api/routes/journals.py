import uuid

from fastapi import APIRouter, status

from app.api.deps import ScopeDep, SessionDep
from app.models import (
    Article,
    ArticleCreate,
    ArticlePublic,
    Journal,
    JournalCreate,
    JournalPublic,
    JournalsPublic,
    MemberPublic,
    MemberUpsert,
)
from app.services import journals

router = APIRouter(prefix="/journals", tags=["journals"])


@router.post("", response_model=JournalPublic, status_code=status.HTTP_201_CREATED)
def create_journal(
    session: SessionDep, scope: ScopeDep, body: JournalCreate
) -> Journal:
    """Creates a journal (administrators only)."""
    return journals.create_journal(session, scope, body)


@router.get("", response_model=JournalsPublic)
def list_journals(session: SessionDep, scope: ScopeDep) -> JournalsPublic:
    """Lists journals the caller can access."""
    data = journals.list_journals(session, scope)
    return JournalsPublic(data=data, count=len(data))


@router.get("/{journal_id}", response_model=JournalPublic)
def read_journal(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID
) -> JournalPublic:
    journal = journals.get_journal(session, scope, journal_id)
    return JournalPublic(
        id=journal.id,
        code=journal.code,
        name=journal.name,
        role=scope.journal_roles.get(journal.id),
    )


@router.get("/{journal_id}/members", response_model=list[MemberPublic])
def list_members(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID
) -> list[MemberPublic]:
    """Lists the journal's members (administrators only)."""
    return journals.list_members(session, scope, journal_id)


@router.put("/{journal_id}/members", response_model=MemberPublic)
def set_member(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID, body: MemberUpsert
) -> MemberPublic:
    """Adds a member to the journal or changes their role."""
    return journals.set_member(session, scope, journal_id, body.email, body.role)


@router.delete(
    "/{journal_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Removes a member from the journal (administrators only)."""
    journals.remove_member(session, scope, journal_id, user_id)


@router.post(
    "/{journal_id}/articles",
    response_model=ArticlePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_article(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID, body: ArticleCreate
) -> Article:
    return journals.create_article(session, scope, journal_id, body)


@router.get("/{journal_id}/articles", response_model=list[ArticlePublic])
def list_articles(
    session: SessionDep, scope: ScopeDep, journal_id: uuid.UUID
) -> list[Article]:
    return journals.list_articles(session, scope, journal_id)
