"""Journals, memberships and articles."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

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
from app.services.access import PENDING_SUB_PREFIX, pending_sub, require


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
    """Adds a person to a journal or changes their role.

    Someone who has not signed in yet is added as a pending user keyed by their
    email; they claim the membership when they first sign in with that address.
    """
    require(scope, journal_id, Action.MANAGE_JOURNAL)
    get_journal(session, scope, journal_id)
    user = session.exec(
        select(User).where(func.lower(col(User.email)) == email.strip().lower())
    ).first()
    if user is None:
        user = User(sub=pending_sub(email), email=email.strip(), is_active=True)
        session.add(user)
        session.flush()
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
    return _member_public(user, role)


def list_members(
    session: Session, scope: Scope, journal_id: uuid.UUID
) -> list[MemberPublic]:
    """Lists a journal's members (administrators only)."""
    require(scope, journal_id, Action.MANAGE_JOURNAL)
    get_journal(session, scope, journal_id)
    rows = session.exec(
        select(JournalMember, User)
        .join(User, col(User.id) == col(JournalMember.user_id))
        .where(JournalMember.journal_id == journal_id)
        .order_by(func.lower(col(User.email)))
    )
    return [_member_public(user, member.role) for member, user in rows]


def remove_member(
    session: Session, scope: Scope, journal_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Removes a person from a journal (administrators only)."""
    require(scope, journal_id, Action.MANAGE_JOURNAL)
    get_journal(session, scope, journal_id)
    member = session.exec(
        select(JournalMember).where(
            JournalMember.journal_id == journal_id, JournalMember.user_id == user_id
        )
    ).first()
    if member is None:
        raise NotFoundError("that person is not a member of this journal")
    session.delete(member)
    session.commit()


def _member_public(user: User, role: Role) -> MemberPublic:
    return MemberPublic(
        user_id=user.id,
        email=user.email,
        role=role,
        full_name=user.full_name,
        pending=user.sub.startswith(PENDING_SUB_PREFIX),
    )


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
