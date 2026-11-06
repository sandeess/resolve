import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.domain.policy import Role, Scope
from app.llm.base import LlmError
from app.models import Article, Chunk, Journal
from app.rag.retrieval import Hit, hybrid_search
from tests.integration.conftest import (
    FakeEmbedder,
    FakeVerifier,
    ScriptedChat,
    add_member,
    auth,
    make_journal,
    make_user,
)

API = "/api/v1"
ANSWER = "Use the Vancouver style for medical manuscripts."


class Team:
    """A journal with one user per role, each with a bearer token."""

    def __init__(
        self, session: Session, verifier: FakeVerifier, code: str = "JA"
    ) -> None:
        self.journal: Journal = make_journal(session, code)
        self.tokens: dict[str, str] = {}
        for role in Role:
            name = f"{role.value}_{code}"
            add_member(session, self.journal, make_user(session, name), role)
            self.tokens[role.value] = verifier.add(name)

    def headers(self, role: str) -> dict[str, str]:
        return auth(self.tokens[role])


def _create(
    client: TestClient, team: Team, role: str = "viewer", **body: Any
) -> dict[str, Any]:
    payload = {"title": "How do we cite medical papers?", **body}
    response = client.post(
        f"{API}/journals/{team.journal.id}/tickets",
        json=payload,
        headers=team.headers(role),
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def _post(client: TestClient, team: Team, role: str, path: str, **body: Any) -> Any:
    return client.post(f"{API}{path}", json=body, headers=team.headers(role))


def _chunk_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Chunk)).one()


def _search(
    session: Session,
    embedder: FakeEmbedder,
    journal_id: uuid.UUID,
    article_id: uuid.UUID | None = None,
) -> list[Hit]:
    """Retrieval as a global admin, so only the journal/article filters apply."""
    question = "Which style for medical papers?"
    return hybrid_search(
        session,
        Scope(is_admin=True),
        journal_id=journal_id,
        query=question,
        query_vector=embedder.embed([question])[0],
        article_id=article_id,
    )


def _ask(
    client: TestClient, team: Team, role: str = "viewer", **body: Any
) -> dict[str, Any]:
    response = client.post(
        f"{API}/journals/{team.journal.id}/ask",
        json={"question": "Which style for medical papers?", **body},
        headers=team.headers(role),
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_anyone_in_the_journal_can_raise_a_ticket(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    ticket = _create(client, team, "viewer", description="Which style?")
    assert ticket["status"] == "open" and ticket["number"] >= 1
    assert ticket["created_by_email"] == "viewer_JA@example.com"

    outsider = verifier.add("outsider")
    response = client.post(
        f"{API}/journals/{team.journal.id}/tickets",
        json={"title": "Let me in"},
        headers=auth(outsider),
    )
    assert response.status_code == 403


def test_ticket_article_must_belong_to_the_journal(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team, other = Team(session, verifier, "JA"), Team(session, verifier, "JB")
    foreign = Article(journal_id=other.journal.id, manuscript_id="M1", title="x")
    session.add(foreign)
    session.commit()
    response = client.post(
        f"{API}/journals/{team.journal.id}/tickets",
        json={"title": "Wrong article", "article_id": str(foreign.id)},
        headers=team.headers("viewer"),
    )
    assert response.status_code == 404


def test_answer_is_searchable_only_after_lead_approval_and_withdrawn_on_reopen(
    client: TestClient,
    session: Session,
    verifier: FakeVerifier,
    chat: ScriptedChat,
) -> None:
    team = Team(session, verifier)
    ticket = _create(client, team, "viewer")
    tid = ticket["id"]
    chat.reply = json.dumps(
        {"sufficient": True, "answer": "Vancouver [1].", "citations": [1]}
    )

    resolved = _post(
        client, team, "assistant", f"/tickets/{tid}/resolve", answer=ANSWER
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert _chunk_count(session) == 0
    assert (
        _ask(client, team)["abstained"] is True
    )  # unapproved answers are not knowledge

    approved = _post(client, team, "lead", f"/tickets/{tid}/approve")
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "closed"
    assert body["resolution"]["approved_by_email"] == "lead_JA@example.com"
    assert _chunk_count(session) == 1

    answer = _ask(client, team)
    assert answer["abstained"] is False
    (citation,) = answer["citations"]
    assert citation["source_type"] == "ticket"
    assert citation["ticket_number"] == ticket["number"]
    assert citation["source_name"] == f"T-{ticket['number']}"
    assert "Vancouver" in citation["snippet"]
    assert f"T-{ticket['number']}" in chat.calls[-1][1]

    reopened = _post(client, team, "assistant", f"/tickets/{tid}/reopen")
    assert reopened.json()["status"] == "open"
    assert reopened.json()["resolution"]["approved_by_email"] is None
    assert _chunk_count(session) == 0
    assert _ask(client, team)["abstained"] is True


def test_lead_can_resolve_and_approve_in_one_step(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    tid = _create(client, team)["id"]
    response = _post(
        client, team, "lead", f"/tickets/{tid}/resolve", answer=ANSWER, approve=True
    )
    assert response.json()["status"] == "closed"
    assert _chunk_count(session) == 1


def test_role_boundaries_on_the_workflow(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    tid = _create(client, team)["id"]

    assert (
        _post(
            client, team, "viewer", f"/tickets/{tid}/resolve", answer=ANSWER
        ).status_code
        == 403
    )
    assert (
        _post(
            client,
            team,
            "assistant",
            f"/tickets/{tid}/resolve",
            answer=ANSWER,
            approve=True,
        ).status_code
        == 403
    )
    _post(client, team, "assistant", f"/tickets/{tid}/resolve", answer=ANSWER)
    assert (
        _post(client, team, "assistant", f"/tickets/{tid}/approve").status_code == 403
    )
    assert _post(client, team, "viewer", f"/tickets/{tid}/reopen").status_code == 403


def test_state_machine_conflicts(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    tid = _create(client, team)["id"]

    assert (
        _post(client, team, "lead", f"/tickets/{tid}/approve").status_code == 409
    )  # nothing to approve
    assert (
        _post(client, team, "lead", f"/tickets/{tid}/reopen").status_code == 409
    )  # already open
    _post(client, team, "lead", f"/tickets/{tid}/resolve", answer=ANSWER, approve=True)
    assert (
        _post(
            client, team, "lead", f"/tickets/{tid}/resolve", answer="Changed my mind."
        ).status_code
        == 409
    )


def test_embedding_failure_leaves_the_ticket_resolved_and_unindexed(
    client: TestClient, session: Session, verifier: FakeVerifier, embedder: FakeEmbedder
) -> None:
    team = Team(session, verifier)
    tid = _create(client, team)["id"]

    def boom(_texts: list[str]) -> list[list[float]]:
        raise LlmError("gateway down")

    embedder.embed = boom  # type: ignore[method-assign,assignment]
    response = _post(
        client, team, "lead", f"/tickets/{tid}/resolve", answer=ANSWER, approve=True
    )
    assert response.status_code == 502
    session.expire_all()
    detail = client.get(f"{API}/tickets/{tid}", headers=team.headers("lead")).json()
    assert detail["status"] == "open" and detail["resolution"] is None
    assert _chunk_count(session) == 0


def test_approved_tickets_never_leak_across_journals_or_articles(
    client: TestClient, session: Session, verifier: FakeVerifier, embedder: FakeEmbedder
) -> None:
    team_a, team_b = Team(session, verifier, "JA"), Team(session, verifier, "JB")
    tid = _create(client, team_b)["id"]
    _post(
        client, team_b, "lead", f"/tickets/{tid}/resolve", answer=ANSWER, approve=True
    )
    assert _search(session, embedder, team_a.journal.id) == []  # B's ticket, A's search

    article = Article(journal_id=team_a.journal.id, manuscript_id="M1", title="Paper")
    session.add(article)
    session.commit()
    scoped = _create(client, team_a, article_id=str(article.id))["id"]
    _post(
        client,
        team_a,
        "lead",
        f"/tickets/{scoped}/resolve",
        answer=ANSWER,
        approve=True,
    )
    # An article-level ticket is invisible to a journal-wide search...
    assert _search(session, embedder, team_a.journal.id) == []
    # ...and found when that article is selected.
    hits = _search(session, embedder, team_a.journal.id, article_id=article.id)
    assert [h.ticket_id for h in hits] == [uuid.UUID(scoped)]
    assert hits[0].source_type == "ticket"


def test_assign_and_prioritise(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    tid = _create(client, team)["id"]
    url = f"{API}/tickets/{tid}"

    assert (
        client.patch(
            url, json={"priority": "high"}, headers=team.headers("viewer")
        ).status_code
        == 403
    )
    both = client.patch(
        url,
        json={"assign_to_me": True, "unassign": True},
        headers=team.headers("assistant"),
    )
    assert both.status_code == 400
    taken = client.patch(
        url,
        json={"assign_to_me": True, "priority": "high"},
        headers=team.headers("assistant"),
    )
    assert taken.json()["assignee_email"] == "assistant_JA@example.com"
    assert taken.json()["priority"] == "high"
    cleared = client.patch(
        url, json={"unassign": True}, headers=team.headers("assistant")
    )
    assert cleared.json()["assignee_email"] is None


def test_who_may_comment(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team = Team(session, verifier)
    other_viewer = make_user(session, "other_viewer")
    add_member(session, team.journal, other_viewer, Role.VIEWER)
    tid = _create(client, team, "viewer")["id"]

    def comment(token: str) -> int:
        response = client.post(
            f"{API}/tickets/{tid}/messages",
            json={"body": "Any update?"},
            headers=auth(token),
        )
        return int(response.status_code)

    assert comment(team.tokens["viewer"]) == 200  # the author
    assert comment(team.tokens["assistant"]) == 200  # the team
    assert comment(verifier.add("other_viewer")) == 403  # a bystander
    thread = client.get(f"{API}/tickets/{tid}", headers=team.headers("lead")).json()[
        "messages"
    ]
    assert [m["author_email"] for m in thread] == [
        "viewer_JA@example.com",
        "assistant_JA@example.com",
    ]


def test_listing_is_scoped_filtered_and_newest_first(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    team, other = Team(session, verifier, "JA"), Team(session, verifier, "JB")
    first, second = (
        _create(client, team, title="First question"),
        _create(client, team, title="Second question"),
    )
    _create(client, other, title="Other journal")
    _post(
        client,
        team,
        "lead",
        f"/tickets/{first['id']}/resolve",
        answer=ANSWER,
        approve=True,
    )

    everything = client.get(
        f"{API}/journals/{team.journal.id}/tickets", headers=team.headers("viewer")
    ).json()
    assert [t["title"] for t in everything["data"]] == [
        "Second question",
        "First question",
    ]
    closed = client.get(
        f"{API}/journals/{team.journal.id}/tickets?status=closed",
        headers=team.headers("viewer"),
    ).json()
    assert [t["id"] for t in closed["data"]] == [first["id"]]
    assert (
        client.get(
            f"{API}/journals/{other.journal.id}/tickets", headers=team.headers("viewer")
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"{API}/tickets/{second['id']}", headers=other.headers("lead")
        ).status_code
        == 404  # invisible under RLS: existence is not confirmed
    )
