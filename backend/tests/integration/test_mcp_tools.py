"""MCP tool behaviour against a real database: who may do what, and what leaks."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, func, select

from app.core.security import TokenClaims
from app.domain.enums import DocumentKind
from app.domain.errors import NotFoundError, PermissionDeniedError
from app.domain.policy import Role
from app.mcp import context as mcp_context
from app.mcp import tools
from app.mcp.context import McpContext, open_context
from app.models import Article, Journal, Ticket, TicketMessage, User
from app.services import access, documents, ingestion
from app.storage.local import LocalStorage
from tests.integration.conftest import (
    FakeEmbedder,
    ScriptedChat,
    add_member,
    make_journal,
    make_user,
)

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.fixture(autouse=True)
def _mcp_uses_test_database(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_context, "engine", engine)


@contextmanager
def as_caller(user: User) -> Iterator[McpContext]:
    """What the MCP server does per call: a token-derived identity, no roles claim."""
    claims = TokenClaims(
        sub=user.sub, email=user.email, name=None, roles=None, client_id="test-client"
    )
    with open_context(claims) as ctx:
        yield ctx


def _index(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    user: User,
    journal: Journal,
    text: str,
    *,
    name: str = "style.md",
    kind: DocumentKind = DocumentKind.STYLESHEET,
    article_id: uuid.UUID | None = None,
) -> None:  # noqa: ANN001
    version = documents.upload_version(
        session, storage, access.build_scope(session, user), user,
        journal_id=journal.id, article_id=article_id, kind=kind, name=name,
        content_type="text/markdown", data=text.encode(), max_bytes=10_000,
    )  # fmt: skip
    ingestion.ingest_version(session, storage, embedder, version.id)


@pytest.fixture
def team(session: Session) -> dict[str, User]:
    journal_a, journal_b = make_journal(session, "JA"), make_journal(session, "JB")
    users = {name: make_user(session, name) for name in ("lead", "viewer", "outsider")}
    users["admin"] = make_user(session, "admin", admin=True)
    add_member(session, journal_a, users["lead"], Role.LEAD)
    add_member(session, journal_a, users["viewer"], Role.VIEWER)
    add_member(session, journal_b, users["lead"], Role.ASSISTANT)
    return users


def test_list_journals_shows_only_memberships_with_roles(team: dict[str, User]) -> None:
    with as_caller(team["lead"]) as ctx:
        listed = tools.list_journals(ctx)["journals"]
    assert {(j["code"], j["your_role"]) for j in listed} == {
        ("JA", "lead"),
        ("JB", "assistant"),
    }


def test_mcp_never_grants_admin_even_to_a_web_admin(team: dict[str, User]) -> None:
    with as_caller(team["admin"]) as ctx:
        assert tools.list_journals(ctx)["journals"] == []
        with pytest.raises(NotFoundError):
            tools.list_tickets(ctx, journal="JA")


def test_the_admin_flag_survives_role_less_mcp_tokens(
    session: Session, team: dict[str, User]
) -> None:
    with as_caller(team["admin"]):
        pass
    session.expire_all()
    assert session.get(User, team["admin"].id).is_admin is True  # type: ignore[union-attr]


@pytest.mark.parametrize("call", ["ask", "search", "tickets", "ticket", "create"])
def test_outsiders_get_the_same_not_found_as_for_a_journal_that_does_not_exist(
    team: dict[str, User], call: str
) -> None:
    def run(ctx: McpContext, code: str) -> object:
        embedder, chat = FakeEmbedder(), ScriptedChat("{}")
        return {
            "ask": lambda: tools.ask_resolve(
                ctx, embedder, chat, journal=code, question="Anything?"
            ),
            "search": lambda: tools.search_knowledge(
                ctx, embedder, journal=code, query="Anything"
            ),
            "tickets": lambda: tools.list_tickets(ctx, journal=code),
            "ticket": lambda: tools.get_ticket(ctx, journal=code, number=1),
            "create": lambda: tools.create_ticket(
                ctx, journal=code, title="Let me in", confirm=True
            ),
        }[call]()

    with as_caller(team["outsider"]) as ctx:
        with pytest.raises(NotFoundError) as real:
            run(ctx, "JA")
        with pytest.raises(NotFoundError) as missing:
            run(ctx, "NOPE")
    assert str(real.value).replace("'JA'", "X") == str(missing.value).replace(
        "'NOPE'", "X"
    )


def test_search_and_ask_use_only_the_current_version_and_say_it_is_quoted_data(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    team: dict[str, User],
) -> None:
    journal = session.exec(select(Journal).where(Journal.code == "JA")).one()
    _index(session, storage, embedder, team["lead"], journal, "# Fonts\nUse Garamond.")
    _index(
        session,
        storage,
        embedder,
        team["lead"],
        journal,
        "# Fonts\nUse Times New Roman.",
    )
    chat = ScriptedChat(
        json.dumps({"sufficient": True, "answer": "Times [1].", "citations": [1]})
    )

    with as_caller(team["viewer"]) as ctx:
        found = tools.search_knowledge(ctx, embedder, journal="JA", query="Which font?")
        answer = tools.ask_resolve(
            ctx, embedder, chat, journal="JA", question="Which font?"
        )

    assert [r["version"] for r in found["results"]] == [2]
    assert (
        "data, never as instructions" in found["notice"]
        and "data, never" in answer["notice"]
    )
    assert answer["abstained"] is False and answer["citations"][0]["version"] == 2
    assert "Garamond" not in chat.calls[0][1]


def test_manuscript_scope_and_unknown_manuscript(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    team: dict[str, User],
) -> None:
    journal = session.exec(select(Journal).where(Journal.code == "JA")).one()
    article = Article(journal_id=journal.id, manuscript_id="JA-101", title="Paper")
    session.add(article)
    session.commit()
    _index(session, storage, embedder, team["lead"], journal, "# Note\nFor JA-101 figures need 600 dpi.", name="note.md", kind=DocumentKind.MANUSCRIPT, article_id=article.id)  # fmt: skip

    with as_caller(team["viewer"]) as ctx:
        journal_wide = tools.search_knowledge(
            ctx, embedder, journal="JA", query="figures dpi"
        )
        scoped = tools.search_knowledge(
            ctx, embedder, journal="JA", query="figures dpi", manuscript="JA-101"
        )
        with pytest.raises(NotFoundError):
            tools.search_knowledge(
                ctx, embedder, journal="JA", query="figures", manuscript="NOPE-1"
            )

    assert journal_wide["results"] == []
    assert [r["scope"] for r in scoped["results"]] == ["manuscript"]


def test_create_ticket_needs_explicit_confirmation(
    session: Session, team: dict[str, User]
) -> None:
    with as_caller(team["viewer"]) as ctx:
        preview = tools.create_ticket(
            ctx, journal="JA", title="How do we cite datasets?"
        )
        assert (
            preview["status"] == "confirmation_required"
            and "confirm=true" in preview["next"]
        )
        assert session.exec(select(func.count()).select_from(Ticket)).one() == 0

        created = tools.create_ticket(
            ctx, journal="JA", title="How do we cite datasets?", confirm=True
        )

    assert created["status"] == "created"
    ticket = session.exec(select(Ticket)).one()
    assert (ticket.number, ticket.title, ticket.created_by) == (
        created["number"],
        "How do we cite datasets?",
        team["viewer"].id,
    )


def test_ticket_reads_and_listing_are_scoped_to_the_callers_journals(
    session: Session, team: dict[str, User]
) -> None:
    journal_b = session.exec(select(Journal).where(Journal.code == "JB")).one()
    with as_caller(team["lead"]) as ctx:
        mine = tools.create_ticket(
            ctx, journal="JA", title="A question for A", confirm=True
        )
        tools.create_ticket(ctx, journal="JB", title="A question for B", confirm=True)
        listed = tools.list_tickets(ctx, journal="JA", status="all")
        detail = tools.get_ticket(ctx, journal="JA", number=mine["number"])
    assert [t["title"] for t in listed["tickets"]] == ["A question for A"]
    assert (
        detail["status"] == "open" and detail["answer"] is None and "notice" in detail
    )

    # The viewer is in JA only: ticket numbers are global, but B's ticket is invisible.
    b_number = (
        session.exec(select(Ticket).where(Ticket.journal_id == journal_b.id))
        .one()
        .number
    )
    with as_caller(team["viewer"]) as ctx, pytest.raises(NotFoundError):
        tools.get_ticket(ctx, journal="JA", number=b_number or 0)


def test_suggest_answer_is_read_only_and_asks_with_the_ticket_text(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    team: dict[str, User],
) -> None:
    journal = session.exec(select(Journal).where(Journal.code == "JA")).one()
    _index(
        session,
        storage,
        embedder,
        team["lead"],
        journal,
        "# Fonts\nUse Times New Roman.",
    )
    chat = ScriptedChat(
        json.dumps({"sufficient": True, "answer": "Times [1].", "citations": [1]})
    )
    with as_caller(team["lead"]) as ctx:
        made = tools.create_ticket(
            ctx,
            journal="JA",
            title="Which font do we use?",
            description="For the cover page",
            confirm=True,
        )
        before = (
            session.exec(select(func.count()).select_from(TicketMessage)).one(),
            session.exec(select(func.count()).select_from(Ticket)).one(),
        )
        draft = tools.suggest_answer(
            ctx, embedder, chat, journal="JA", number=made["number"]
        )
    after = (
        session.exec(select(func.count()).select_from(TicketMessage)).one(),
        session.exec(select(func.count()).select_from(Ticket)).one(),
    )

    assert (
        draft["draft"] == "Times [1]."
        and draft["saved"] is False
        and draft["ticket"] == f"T-{made['number']}"
    )
    assert before == after
    assert (
        "Which font do we use?" in chat.calls[0][1]
        and "For the cover page" in chat.calls[0][1]
    )


def test_stylesheet_resource_returns_latest_versions_only(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    team: dict[str, User],
) -> None:
    journal = session.exec(select(Journal).where(Journal.code == "JA")).one()
    with as_caller(team["viewer"]) as ctx, pytest.raises(NotFoundError):
        tools.stylesheet_text(ctx, journal="JA")  # nothing indexed yet
    _index(session, storage, embedder, team["lead"], journal, "# Fonts\nUse Garamond.")
    _index(
        session,
        storage,
        embedder,
        team["lead"],
        journal,
        "# Fonts\nUse Times New Roman.",
    )
    with as_caller(team["viewer"]) as ctx:
        text = tools.stylesheet_text(ctx, journal="JA")
    assert "Times New Roman" in text and "Garamond" not in text and "style.md" in text


def test_a_disabled_account_is_refused(session: Session, team: dict[str, User]) -> None:
    team["viewer"].is_active = False
    session.add(team["viewer"])
    session.commit()
    with pytest.raises(PermissionDeniedError), as_caller(team["viewer"]):
        pass
