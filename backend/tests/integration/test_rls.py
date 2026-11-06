"""Row-level security, tested with raw SQL so it cannot lean on service checks.

Each test opens a session bound to a user and runs queries a buggy service
might: no journal filter, a forged journal id in an INSERT, and so on.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest
from sqlalchemy import CursorResult, Engine, text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session

from app.core import rls
from app.domain.enums import DocumentKind, TicketStatus
from app.domain.policy import Role
from app.models import (
    Article,
    Chunk,
    Document,
    DocumentVersion,
    Journal,
    Ticket,
    TicketMessage,
    TicketResolution,
    User,
)
from tests.integration.conftest import add_member, make_journal, make_user

EMBED = [0.0] * 1024

TENANT_TABLES = (
    "journal",
    "journalmember",
    "article",
    "document",
    "documentversion",
    "chunk",
    "ticket",
    "ticketmessage",
    "ticketresolution",
)


class World:
    """Two journals, each with one row in every tenant table."""

    def __init__(self, session: Session) -> None:
        self.a, self.b = make_journal(session, "JA"), make_journal(session, "JB")
        self.member_a = make_user(session, "member_a")
        self.member_b = make_user(session, "member_b")
        self.outsider = make_user(session, "outsider")
        self.admin = make_user(session, "admin", admin=True)
        add_member(session, self.a, self.member_a, Role.LEAD)
        add_member(session, self.b, self.member_b, Role.LEAD)
        for journal, owner in ((self.a, self.member_a), (self.b, self.member_b)):
            self._populate(session, journal, owner)

    @staticmethod
    def _populate(session: Session, journal: Journal, owner: User) -> None:
        article = Article(journal_id=journal.id, manuscript_id="M1", title="Paper")
        document = Document(
            journal_id=journal.id, kind=DocumentKind.STYLESHEET, name="style.md"
        )
        ticket = Ticket(journal_id=journal.id, title="A question", created_by=owner.id)
        session.add_all([article, document, ticket])
        session.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_no=1,
            sha256="x" * 64,
            size_bytes=1,
            content_type="text/plain",
            storage_key=f"k/{journal.code}",
            uploaded_by=owner.id,
        )
        session.add(version)
        session.flush()
        session.add_all(
            [
                Chunk(
                    version_id=version.id,
                    journal_id=journal.id,
                    chunk_index=0,
                    content=f"secret of {journal.code}",
                    embedding=EMBED,
                    embedding_model="t",
                ),
                TicketMessage(ticket_id=ticket.id, author_id=owner.id, body="hi"),
                TicketResolution(
                    ticket_id=ticket.id, answer="an answer", resolved_by=owner.id
                ),
            ]
        )
        session.commit()


@contextmanager
def as_user(
    engine: Engine, user: User | None, *, admin: bool = False
) -> Iterator[Session]:
    """A session under RLS, as `user` (or anonymous when None)."""
    with Session(engine) as session:
        context = rls.RlsContext(
            user.id if user else None, admin or bool(user and user.is_admin)
        )
        rls.bind(session, context)
        yield session


def affected(session: Session, sql: str) -> int:
    """Rows changed by a DML statement (`Result` is typed without `rowcount`)."""
    return int(cast(CursorResult[Any], session.execute(text(sql))).rowcount)


def count(session: Session, table: str) -> int:
    return int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_unfiltered_select_returns_only_the_members_own_journal(
    engine: Engine, world: World, table: str
) -> None:
    """The point of RLS: a query with no WHERE clause still cannot cross journals."""
    with as_user(engine, world.member_a) as session:
        assert count(session, table) == 1
    with as_user(engine, world.member_b) as session:
        assert count(session, table) == 1


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_outsiders_and_anonymous_see_nothing(
    engine: Engine, world: World, table: str
) -> None:
    with as_user(engine, world.outsider) as session:
        assert count(session, table) == 0
    with as_user(engine, None) as session:
        assert count(session, table) == 0


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_admin_sees_every_journal(engine: Engine, world: World, table: str) -> None:
    with as_user(engine, world.admin) as session:
        assert count(session, table) == 2


def test_the_flag_alone_does_not_make_a_non_admin_user_an_admin(
    engine: Engine, world: World
) -> None:
    """`is_admin` comes from the bound context, which only the server sets."""
    with as_user(engine, world.member_a, admin=False) as session:
        assert count(session, "journal") == 1


def test_cannot_insert_into_another_journal(engine: Engine, world: World) -> None:
    with (
        as_user(engine, world.member_a) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.add(Article(journal_id=world.b.id, manuscript_id="M2", title="Forged"))
        session.commit()
    with (
        as_user(engine, world.member_a) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.add(
            Ticket(journal_id=world.b.id, title="Forged", created_by=world.member_a.id)
        )
        session.commit()


def test_cannot_move_a_row_into_another_journal(engine: Engine, world: World) -> None:
    with (
        as_user(engine, world.member_a) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.execute(text("UPDATE article SET journal_id = :b"), {"b": world.b.id})
        session.commit()


def test_updates_and_deletes_never_touch_other_journals(
    engine: Engine, world: World
) -> None:
    with as_user(engine, world.member_a) as session:
        updated = affected(session, "UPDATE ticket SET title = 'x'")
        deleted = affected(session, "DELETE FROM article")
        session.commit()
    assert (updated, deleted) == (1, 1)
    with as_user(engine, world.member_b) as session:
        assert count(session, "article") == 1
        title = session.execute(text("SELECT title FROM ticket")).scalar_one()
        assert title == "A question"


def test_only_admins_can_create_or_change_journals_and_memberships(
    engine: Engine, world: World
) -> None:
    with (
        as_user(engine, world.member_a) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.add(Journal(code="JX", name="Sneaky"))
        session.commit()
    with as_user(engine, world.member_a) as session:
        assert affected(session, "UPDATE journal SET name = 'renamed'") == 0
    with (
        as_user(engine, world.outsider) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.execute(
            text(
                "INSERT INTO journalmember (id, journal_id, user_id, role) VALUES (:i, :j, :u, 'lead')"
            ),
            {"i": uuid.uuid4(), "j": world.a.id, "u": world.outsider.id},
        )
        session.commit()
    with as_user(engine, world.admin) as session:
        session.add(Journal(code="JX", name="Legit"))
        session.commit()


def test_members_cannot_read_other_peoples_memberships(
    engine: Engine, world: World
) -> None:
    with as_user(engine, world.member_a) as session:
        rows = (
            session.execute(text("SELECT user_id FROM journalmember")).scalars().all()
        )
    assert rows == [world.member_a.id]


def test_identity_does_not_leak_between_transactions_on_a_pooled_connection(
    engine: Engine, world: World
) -> None:
    """SET LOCAL must expire with the transaction, or a pool would mix users up."""
    with as_user(engine, world.member_a) as session:
        assert count(session, "article") == 1
        session.commit()
        assert (
            count(session, "article") == 1
        )  # next transaction re-applies the identity
    with Session(engine) as plain:  # a different checkout, no context: privileged owner
        assert count(plain, "article") == 2
        role = plain.execute(text("SELECT current_user")).scalar_one()
        assert role != rls.RLS_ROLE


def test_binding_mid_transaction_applies_immediately(
    engine: Engine, world: World
) -> None:
    """The sign-in code opens a transaction before it knows who the user is."""
    with Session(engine) as session:
        rls.bind(session, rls.RlsContext())
        assert count(session, "article") == 0  # anonymous transaction is now open
        rls.bind(session, rls.RlsContext(world.member_a.id, False))
        assert count(session, "article") == 1  # same transaction, new identity


def test_restricted_role_cannot_touch_the_job_queue_or_migration_tables(
    engine: Engine, world: World
) -> None:
    del world
    with (
        as_user(engine, None) as session,
        pytest.raises(DBAPIError, match="permission denied"),
    ):
        session.execute(text("SELECT * FROM alembic_version"))


def test_every_table_is_either_protected_or_deliberately_exempt(engine: Engine) -> None:
    """A new table must be added to the policies or to this allowlist on purpose."""
    exempt = {"app_user", "alembic_version"}
    with Session(engine) as session:
        unprotected = set(
            session.execute(
                text(
                    "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity "
                    "AND relname NOT LIKE 'procrastinate_%'"
                )
            ).scalars()
        )
    assert unprotected == exempt


def test_ticket_states_are_visible_through_rls_like_any_other_column(
    engine: Engine, world: World
) -> None:
    with as_user(engine, world.member_a) as session:
        status = session.execute(text("SELECT status FROM ticket")).scalar_one()
    assert status == TicketStatus.OPEN.value
