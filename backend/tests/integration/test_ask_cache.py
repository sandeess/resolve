"""The answer cache must be fast without ever being wrong or leaky."""

import json
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import providers
from app.domain.enums import DocumentKind, TicketPriority, TicketSource
from app.domain.errors import PermissionDeniedError
from app.domain.policy import Role
from app.llm.cache import CachingEmbedder
from app.main import app
from app.models import Article, Journal, TicketCreate, User
from app.rag.ask import AskResult, answer_cache, ask
from app.services import access, documents, ingestion, tickets
from app.storage.local import LocalStorage
from tests.integration.conftest import (
    FakeEmbedder,
    FakeVerifier,
    ScriptedChat,
    add_member,
    auth,
    make_journal,
    make_user,
)

ANSWER = json.dumps(
    {"sufficient": True, "answer": "Use Times New Roman [1].", "citations": [1]}
)
Q = "Which font should we use?"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    answer_cache.clear()
    yield
    answer_cache.clear()


@pytest.fixture
def lead(session: Session) -> tuple[User, Journal]:
    user, journal = make_user(session, "lead"), make_journal(session, "JA")
    add_member(session, journal, user, Role.LEAD)
    return user, journal


def _index(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    user: User,
    journal: Journal,
    text: str,
    *,
    article_id: uuid.UUID | None = None,
) -> None:
    version = documents.upload_version(
        session, storage, access.build_scope(session, user), user,
        journal_id=journal.id, article_id=article_id,
        kind=DocumentKind.STYLESHEET if article_id is None else DocumentKind.MANUSCRIPT,
        name="style.md", content_type="text/markdown", data=text.encode(), max_bytes=10_000,
    )  # fmt: skip
    ingestion.ingest_version(session, storage, embedder, version.id)


def _ask(
    session: Session,
    embedder: FakeEmbedder,
    chat: ScriptedChat,
    user: User,
    journal: Journal,
    question: str = Q,
    **kwargs: object,
) -> AskResult:
    return ask(
        session=session, scope=access.build_scope(session, user), embedder=embedder,
        chat=chat, journal_id=journal.id, question=question, **kwargs,  # type: ignore[arg-type]
    )  # fmt: skip


@pytest.fixture
def ready(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    lead: tuple[User, Journal],
) -> tuple[User, Journal]:
    user, journal = lead
    _index(session, storage, embedder, user, journal, "# Fonts\nUse Times New Roman.")
    return user, journal


def test_a_repeated_question_skips_the_model_and_says_so(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    chat = ScriptedChat(ANSWER)

    first = _ask(session, embedder, chat, user, journal)
    second = _ask(session, embedder, chat, user, journal, "  which FONT should we use ")

    assert len(chat.calls) == 1
    assert first.timings is not None and not first.timings.cached
    assert second.timings is not None and second.timings.cached
    assert second.answer == first.answer and second.citations == first.citations


def test_timings_account_for_each_stage(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    timings = _ask(session, embedder, ScriptedChat(ANSWER), user, journal).timings
    assert timings is not None
    assert (
        timings.total_ms
        >= timings.embed_ms + timings.search_ms + timings.generate_ms - 3
    )  # rounding


def test_use_cache_false_always_runs_the_pipeline(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    chat = ScriptedChat(ANSWER)
    _ask(session, embedder, chat, user, journal, use_cache=False)
    _ask(session, embedder, chat, user, journal, use_cache=False)
    assert len(chat.calls) == 2 and len(answer_cache) == 0


def test_revising_a_document_invalidates_cached_answers(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    ready: tuple[User, Journal],
) -> None:
    user, journal = ready
    chat = ScriptedChat(ANSWER)
    _ask(session, embedder, chat, user, journal)

    # Upload only (not yet indexed): the old version is no longer current, so the
    # cached answer built from it must not be served.
    documents.upload_version(
        session, storage, access.build_scope(session, user), user,
        journal_id=journal.id, article_id=None, kind=DocumentKind.STYLESHEET, name="style.md",
        content_type="text/markdown", data=b"# Fonts\nUse Garamond.", max_bytes=10_000,
    )  # fmt: skip
    after = _ask(session, embedder, chat, user, journal)
    # A stale cache hit would repeat the old answer; instead there are no live
    # sources, so Ask refuses without calling the model.
    assert (
        after.abstained is True and after.reason == "no relevant documents were found"
    )
    assert len(chat.calls) == 1


def test_approving_and_reopening_a_ticket_invalidates_cached_answers(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    scope = access.build_scope(session, user)
    chat = ScriptedChat(ANSWER)
    _ask(session, embedder, chat, user, journal)
    assert len(chat.calls) == 1

    ticket = tickets.create_ticket(
        session,
        scope,
        user,
        journal.id,
        TicketCreate(
            title="Which font for headings?",
            priority=TicketPriority.NORMAL,
            source=TicketSource.WEB,
        ),
    )
    tickets.resolve_ticket(
        session,
        scope,
        user,
        embedder,
        ticket.id,
        answer="Headings use Arial.",
        approve=True,
    )
    _ask(session, embedder, chat, user, journal)
    assert len(chat.calls) == 2  # approval changed what the journal knows

    tickets.reopen_ticket(session, scope, ticket.id)
    _ask(session, embedder, chat, user, journal)
    assert len(chat.calls) == 3  # ...and withdrawing it changes it back


def test_permission_is_checked_before_the_cache(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    chat = ScriptedChat(ANSWER)
    _ask(session, embedder, chat, user, journal)  # now cached

    outsider = make_user(session, "outsider")
    other = make_journal(session, "JB")
    add_member(session, other, outsider, Role.LEAD)
    with pytest.raises(PermissionDeniedError):
        _ask(session, embedder, chat, outsider, journal)

    viewer = make_user(session, "viewer")
    add_member(session, journal, viewer, Role.VIEWER)
    assert _ask(session, embedder, chat, viewer, journal).timings.cached is True  # type: ignore[union-attr]


def test_answers_are_never_shared_across_journals_or_articles(
    session: Session,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    ready: tuple[User, Journal],
) -> None:
    user, journal = ready
    other = make_journal(session, "JB")
    add_member(session, other, user, Role.LEAD)
    _index(session, storage, embedder, user, other, "# Fonts\nUse Courier.")
    article = Article(journal_id=journal.id, manuscript_id="M1", title="Paper")
    session.add(article)
    session.commit()
    chat = ScriptedChat(ANSWER)

    _ask(session, embedder, chat, user, journal)
    _ask(session, embedder, chat, user, other)
    _ask(session, embedder, chat, user, journal, article_id=article.id)
    assert len(chat.calls) == 3  # three different scopes, three real answers


def test_glitches_are_not_cached_but_real_refusals_are(
    session: Session, embedder: FakeEmbedder, ready: tuple[User, Journal]
) -> None:
    user, journal = ready
    chat = ScriptedChat("this is not json")
    assert _ask(session, embedder, chat, user, journal).abstained
    chat.reply = ANSWER
    recovered = _ask(session, embedder, chat, user, journal)
    assert (
        recovered.abstained is False and len(chat.calls) == 2
    )  # the glitch was retried, not remembered

    answer_cache.clear()
    chat2 = ScriptedChat(json.dumps({"sufficient": False}))
    _ask(session, embedder, chat2, user, journal, "What is the weather?")
    _ask(session, embedder, chat2, user, journal, "What is the weather?")
    assert (
        len(chat2.calls) == 1
    )  # "the sources do not answer this" is a stable fact about the knowledge


def test_prefetching_a_question_leaves_only_the_model_call(
    client: TestClient,
    session: Session,
    verifier: FakeVerifier,
) -> None:
    class Counting(FakeEmbedder):
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls += 1
            return super().embed(texts)

    counting = Counting()
    shared = CachingEmbedder(
        counting
    )  # one instance for the whole test, as in production
    app.dependency_overrides[providers.get_embedder] = lambda: shared

    journal, viewer = make_journal(session, "JA"), make_user(session, "viewer")
    add_member(session, journal, viewer, Role.VIEWER)
    token = verifier.add("viewer")
    url = f"/api/v1/journals/{journal.id}/ask"

    prefetch = client.post(url + "/prefetch", json={"question": Q}, headers=auth(token))
    assert prefetch.status_code == 204 and counting.calls == 1

    asked = client.post(url, json={"question": Q}, headers=auth(token))
    assert asked.status_code == 200 and counting.calls == 1  # the embedding was reused
    assert asked.json()["timings"]["embed_ms"] >= 0


def test_prefetch_needs_the_same_permission_as_asking(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    journal = make_journal(session, "JA")
    url = f"/api/v1/journals/{journal.id}/ask/prefetch"
    assert (
        client.post(
            url, json={"question": Q}, headers=auth(verifier.add("stranger"))
        ).status_code
        == 403
    )
    assert (
        client.post(url, json={"question": "x"}, headers=auth("stranger")).status_code
        == 422
    )
    assert client.post(url, json={"question": Q}).status_code == 401
