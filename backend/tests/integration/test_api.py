import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.domain.policy import Role
from app.llm.base import LlmError
from app.services import ingestion
from app.storage.local import LocalStorage
from app.workers.queue import queue
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


def _upload(
    client: TestClient,
    token: str,
    journal_id: uuid.UUID,
    content: bytes,
    kind: str = "stylesheet",
    name: str = "style.docx",
) -> Any:
    response = client.post(
        f"{API}/journals/{journal_id}/documents",
        headers=auth(token),
        files={"file": (name, content, "application/octet-stream")},
        data={"kind": kind},
    )
    return response


def test_requires_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/me", headers=auth("garbage")).status_code == 401


def test_first_login_provisions_user(
    client: TestClient, verifier: FakeVerifier
) -> None:
    body = client.get(f"{API}/me", headers=auth(verifier.add("ann"))).json()
    assert body["email"] == "ann@example.com"
    assert body["is_admin"] is False


def test_only_admin_creates_journals(
    client: TestClient, verifier: FakeVerifier
) -> None:
    payload = {"code": "JA", "name": "Journal A"}
    user, admin = verifier.add("ann"), verifier.add("root", admin=True)

    def create(token: str) -> int:
        response = client.post(f"{API}/journals", json=payload, headers=auth(token))
        return int(response.status_code)

    assert create(user) == 403
    assert create(admin) == 201
    assert create(admin) == 409


def test_users_only_see_their_own_journals(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    ann = make_user(session, "ann")
    ja, jb = make_journal(session, "JA"), make_journal(session, "JB")
    add_member(session, ja, ann, Role.VIEWER)
    token = verifier.add("ann")

    listed = client.get(f"{API}/journals", headers=auth(token)).json()
    assert [j["code"] for j in listed["data"]] == ["JA"]
    assert listed["data"][0]["role"] == "viewer"
    for path in (f"/journals/{jb.id}", f"/journals/{jb.id}/documents"):
        assert client.get(API + path, headers=auth(token)).status_code == 403


def test_documents_cannot_leak_across_journals(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    lead_a, lead_b = make_user(session, "lead_a"), make_user(session, "lead_b")
    ja, jb = make_journal(session, "JA"), make_journal(session, "JB")
    add_member(session, ja, lead_a, Role.LEAD)
    add_member(session, jb, lead_b, Role.LEAD)
    token_a, token_b = verifier.add("lead_a"), verifier.add("lead_b")

    version = _upload(client, token_b, jb.id, b"secret b").json()
    download = f"{API}/document-versions/{version['id']}/download"
    versions = f"{API}/documents/{version['document_id']}/versions"

    # Another journal's rows are invisible (RLS), so by-id lookups are 404, not 403:
    # the answer does not even confirm the document exists.
    assert client.get(download, headers=auth(token_a)).status_code == 404
    assert client.get(versions, headers=auth(token_a)).status_code == 404
    assert client.get(download, headers=auth(token_b)).content == b"secret b"
    assert _upload(client, token_a, jb.id, b"x").status_code == 403


def test_revision_flow_over_http(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    lead, journal = make_user(session, "lead"), make_journal(session, "JA")
    add_member(session, journal, lead, Role.LEAD)
    token = verifier.add("lead")

    v1 = _upload(client, token, journal.id, b"one")
    v2 = _upload(client, token, journal.id, b"two")
    assert (v1.status_code, v2.status_code) == (201, 201)
    assert v2.json()["version_no"] == 2

    listing = client.get(
        f"{API}/journals/{journal.id}/documents", headers=auth(token)
    ).json()
    assert listing["count"] == 1
    assert listing["data"][0]["current_version"]["version_no"] == 2

    versions = client.get(
        f"{API}/documents/{v2.json()['document_id']}/versions", headers=auth(token)
    ).json()
    assert [v["version_no"] for v in versions] == [2, 1]
    assert [v["is_current"] for v in versions] == [True, False]


def test_upload_enqueues_an_ingestion_job_once_per_new_version(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    lead, journal = make_user(session, "lead"), make_journal(session, "JA")
    add_member(session, journal, lead, Role.LEAD)
    token = verifier.add("lead")

    first = _upload(client, token, journal.id, b"# A\none").json()
    _upload(client, token, journal.id, b"# A\ntwo")

    jobs = list(queue.connector.jobs.values())  # type: ignore[attr-defined]
    assert [j["task_name"] for j in jobs] == ["ingest_document_version"] * 2
    assert jobs[0]["args"] == {"version_id": first["id"]}


def test_reindex_requires_upload_permission(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    lead, viewer = make_user(session, "lead"), make_user(session, "viewer")
    journal = make_journal(session, "JA")
    add_member(session, journal, lead, Role.LEAD)
    add_member(session, journal, viewer, Role.VIEWER)
    version = _upload(client, verifier.add("lead"), journal.id, b"# A\none").json()
    url = f"{API}/document-versions/{version['id']}/reindex"

    assert client.post(url, headers=auth(verifier.add("viewer"))).status_code == 403
    assert client.post(url, headers=auth("lead")).status_code == 202


def test_ask_endpoint(
    client: TestClient,
    session: Session,
    verifier: FakeVerifier,
    storage: LocalStorage,
    embedder: FakeEmbedder,
    chat: ScriptedChat,
) -> None:
    lead, viewer, outsider = (make_user(session, n) for n in ("lead", "viewer", "out"))
    journal = make_journal(session, "JA")
    add_member(session, journal, lead, Role.LEAD)
    add_member(session, journal, viewer, Role.VIEWER)
    version = _upload(
        client,
        verifier.add("lead"),
        journal.id,
        b"# Fonts\nUse Times New Roman.",
        name="style.md",
    ).json()
    ingestion.ingest_version(session, storage, embedder, uuid.UUID(version["id"]))
    chat.reply = json.dumps(
        {"sufficient": True, "answer": "Times [1].", "citations": [1]}
    )
    url = f"{API}/journals/{journal.id}/ask"
    body = {"question": "Which font?"}

    ok = client.post(url, json=body, headers=auth(verifier.add("viewer")))
    assert ok.status_code == 200, ok.text
    assert ok.json()["citations"], ok.json()
    assert ok.json()["citations"][0]["source_name"] == "style.md"
    assert (
        client.post(url, json=body, headers=auth(verifier.add("out"))).status_code
        == 403
    )
    assert (
        client.post(url, json={"question": "x"}, headers=auth("viewer")).status_code
        == 422
    )
    assert client.post(url, json=body).status_code == 401


def test_ask_reports_gateway_failure_as_502(
    client: TestClient, session: Session, verifier: FakeVerifier, embedder: FakeEmbedder
) -> None:
    viewer, journal = make_user(session, "viewer"), make_journal(session, "JA")
    add_member(session, journal, viewer, Role.VIEWER)

    def boom(_texts: list[str]) -> list[list[float]]:
        raise LlmError("gateway down")

    embedder.embed = boom  # type: ignore[method-assign,assignment]
    response = client.post(
        f"{API}/journals/{journal.id}/ask",
        json={"question": "Anything?"},
        headers=auth(verifier.add("viewer")),
    )
    assert response.status_code == 502


def test_upload_rejects_unsupported_file_types(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    lead = make_user(session, "lead_types")
    journal = make_journal(session, "JT")
    add_member(session, journal, lead, Role.LEAD)
    token = verifier.add("lead_types")

    for name in ("run.exe", "photo.png", "archive.zip", "noextension"):
        response = _upload(client, token, journal.id, b"x", name=name)
        assert response.status_code == 415, name
    assert _upload(client, token, journal.id, b"x", name="rules.md").status_code == 201
