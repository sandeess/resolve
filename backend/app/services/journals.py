"""Journals, memberships and articles."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.domain.policy import Action, Role, Scope
from app.models import (
    Article,
    ArticleCreate,
    Journal,
    JournalCreate,
    JournalMember,
    JournalPublic,
    MemberPublic,
    User,
)
from app.services.access import require


def create_journal(session: Session, scope: Scope, data: JournalCreate) -> Journal:
    """Creates a journal. Only global administrators may do this."""
    if not scope.is_admin:
        raise PermissionDeniedError("only administrators can create journals")
    journal = Journal.model_validate(data)
    session.add(journal)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(f"journal code {data.code!r} already exists") from exc
    session.refresh(journal)
    return journal


def list_journals(session: Session, scope: Scope) -> list[JournalPublic]:
    """Lists the journals visible to `scope`, with the caller's role in each."""
    query = select(Journal).order_by(col(Journal.code))
    if not scope.is_admin:
        query = query.where(col(Journal.id).in_(scope.journal_ids))
    return [
        JournalPublic(
            id=j.id, code=j.code, name=j.name, role=scope.journal_roles.get(j.id)
        )
        for j in session.exec(query)
    ]


def get_journal(session: Session, scope: Scope, journal_id: uuid.UUID) -> Journal:
    """Returns a journal the caller may read, else raises."""
    require(scope, journal_id, Action.READ)
    journal = session.get(Journal, journal_id)
    if journal is None:
        raise NotFoundError("journal not found")
    return journal


def set_member(
    session: Session, scope: Scope, journal_id: uuid.UUID, email: str, role: Role
) -> MemberPublic:
    """Adds a user to a journal or changes their role.

    The user must already have signed in once, so that a row exists for them.
    """
    require(scope, journal_id, Action.MANAGE_JOURNAL)
    get_journal(session, scope, journal_id)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise NotFoundError(f"no user with email {email!r}; they must sign in first")
    member = session.exec(
        select(JournalMember).where(
            JournalMember.journal_id == journal_id, JournalMember.user_id == user.id
        )
    ).first()
    if member is None:
        member = JournalMember(journal_id=journal_id, user_id=user.id, role=role)
    else:
        member.role = role
    session.add(member)
    session.commit()
    return MemberPublic(user_id=user.id, email=user.email, role=role)


def create_article(
    session: Session, scope: Scope, journal_id: uuid.UUID, data: ArticleCreate
) -> Article:
    """Registers an article (manuscript) under a journal."""
    require(scope, journal_id, Action.UPLOAD_CONTENT)
    get_journal(session, scope, journal_id)
    article = Article.model_validate(data, update={"journal_id": journal_id})
    session.add(article)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            f"manuscript {data.manuscript_id!r} already exists in this journal"
        ) from exc
    session.refresh(article)
    return article


def list_articles(
    session: Session, scope: Scope, journal_id: uuid.UUID
) -> list[Article]:
    require(scope, journal_id, Action.READ)
    return list(
        session.exec(
            select(Article)
            .where(Article.journal_id == journal_id)
            .order_by(col(Article.manuscript_id))
        )
    )
