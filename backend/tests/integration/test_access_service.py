from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import Engine
from sqlmodel import Session, func, select

from app.core.security import TokenClaims
from app.models import User
from app.services import access


def _claims(
    email: str = "ann@example.com", roles: frozenset[str] | None = frozenset()
) -> TokenClaims:
    return TokenClaims(sub="sub-1", email=email, name="Ann", roles=roles)


def test_concurrent_first_logins_create_one_user(
    engine: Engine, session: Session
) -> None:
    """A browser fires several API calls at once on first login."""
    workers = 8
    barrier = Barrier(workers)

    def login(_: int) -> str:
        with Session(engine) as s:
            barrier.wait()
            return str(access.provision_user(s, _claims(), admin_role="r").id)

    with ThreadPoolExecutor(workers) as pool:
        ids = set(pool.map(login, range(workers)))

    assert len(ids) == 1
    assert session.exec(select(func.count()).select_from(User)).one() == 1


def test_claims_changes_are_synced(session: Session) -> None:
    access.provision_user(session, _claims(), admin_role="admin")
    user = access.provision_user(
        session, _claims("new@example.com", frozenset({"admin"})), admin_role="admin"
    )
    assert user.email == "new@example.com"
    assert user.is_admin is True


def test_a_token_without_role_claims_never_demotes_an_admin(session: Session) -> None:
    """Dynamically registered (MCP) clients get tokens with no role claim at all."""
    access.provision_user(
        session, _claims(roles=frozenset({"admin"})), admin_role="admin"
    )
    user = access.provision_user(session, _claims(roles=None), admin_role="admin")
    assert user.is_admin is True
    # ...while an explicit "no roles" token (a real demotion) still demotes.
    user = access.provision_user(
        session, _claims(roles=frozenset()), admin_role="admin"
    )
    assert user.is_admin is False


def test_a_new_user_from_a_roleless_token_is_not_an_admin(session: Session) -> None:
    assert (
        access.provision_user(session, _claims(roles=None), admin_role="admin").is_admin
        is False
    )
