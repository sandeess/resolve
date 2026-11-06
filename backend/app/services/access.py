"""User provisioning and authorization scope construction."""

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.security import TokenClaims
from app.domain.errors import PermissionDeniedError
from app.domain.policy import Action, Scope
from app.models import JournalMember, User, utc_now

#: `User.sub` of someone an administrator added by email before they ever signed
#: in. At their first sign-in the row is claimed (the sub is replaced by theirs).
PENDING_SUB_PREFIX = "pending:"


def pending_sub(email: str) -> str:
    return f"{PENDING_SUB_PREFIX}{email.strip().lower()}"


def provision_user(session: Session, claims: TokenClaims, *, admin_role: str) -> User:
    """Returns the user for `claims`, creating or refreshing the row as needed.

    A browser fires several API calls at once on first login, so creation must
    be safe under concurrency: the insert ignores a lost race and we re-read.
    """
    # Roles unknown (no role claim): keep whatever is stored, never demote.
    admin_claim = None if claims.roles is None else admin_role in claims.roles
    is_admin = bool(admin_claim)
    _claim_pending(session, claims)
    session.execute(
        insert(User)
        .values(
            id=uuid.uuid4(),
            sub=claims.sub,
            email=claims.email,
            full_name=claims.name,
            is_admin=is_admin,
            is_active=True,
            created_at=utc_now(),
        )
        .on_conflict_do_nothing(index_elements=["sub"])
    )
    session.commit()
    user = session.exec(select(User).where(User.sub == claims.sub)).one()
    new_admin = user.is_admin if admin_claim is None else admin_claim
    if (user.email, user.full_name, user.is_admin) != (
        claims.email,
        claims.name,
        new_admin,
    ):
        user.email, user.full_name, user.is_admin = claims.email, claims.name, new_admin
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _claim_pending(session: Session, claims: TokenClaims) -> None:
    """Hands memberships added by email to the person who now signs in with it."""
    if session.exec(select(User.id).where(User.sub == claims.sub)).first():
        return
    pending = session.exec(
        select(User).where(User.sub == pending_sub(claims.email))
    ).first()
    if pending is not None:
        pending.sub = claims.sub
        session.add(pending)
        session.commit()


def build_scope(session: Session, user: User) -> Scope:
    """Loads the user's journal memberships into an immutable `Scope`."""
    rows = session.exec(
        select(JournalMember).where(JournalMember.user_id == user.id)
    ).all()
    return Scope(
        is_admin=user.is_admin,
        journal_roles={row.journal_id: row.role for row in rows},
    )


def require(scope: Scope, journal_id: uuid.UUID, action: Action) -> None:
    """Raises `PermissionDeniedError` unless `scope` allows `action` in the journal."""
    if not scope.allows(journal_id, action):
        raise PermissionDeniedError(f"not allowed to {action.value} in this journal")
