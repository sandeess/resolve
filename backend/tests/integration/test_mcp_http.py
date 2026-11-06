"""The MCP server over HTTP: authentication, OAuth discovery, and a real tool call."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, func, select
from starlette.testclient import TestClient

from app.core import providers
from app.domain.policy import Role
from app.mcp import context as mcp_context
from app.mcp.server import app as mcp_app
from app.models import Ticket
from tests.integration.conftest import (
    FakeEmbedder,
    FakeVerifier,
    ScriptedChat,
    add_member,
    make_journal,
    make_user,
)

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
EXPECTED_TOOLS = {
    "list_journals",
    "ask_resolve",
    "search_knowledge",
    "list_tickets",
    "get_ticket",
    "suggest_answer",
    "create_ticket",
}


@pytest.fixture
def mcp(
    engine: Engine,
    clean_db: None,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, FakeVerifier]]:
    verifier = FakeVerifier()
    monkeypatch.setattr(mcp_context, "engine", engine)
    monkeypatch.setattr(providers, "get_verifier", lambda: verifier)
    monkeypatch.setattr(providers, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(providers, "get_chat_model", lambda: ScriptedChat("{}"))
    with TestClient(mcp_app) as client:
        yield client, verifier


def rpc(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def body(response: Any) -> dict[str, Any]:
    """The JSON-RPC message, whether the server answered as JSON or as an SSE stream."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        data = next(
            line[5:] for line in response.text.splitlines() if line.startswith("data:")
        )
        return json.loads(data)  # type: ignore[no-any-return]
    return response.json()  # type: ignore[no-any-return]


def call(client: TestClient, token: str, tool: str, **arguments: Any) -> dict[str, Any]:
    result: dict[str, Any] = body(
        rpc(client, "tools/call", {"name": tool, "arguments": arguments}, token)
    )["result"]
    return result


def test_requests_without_a_token_are_challenged_with_the_discovery_url(
    mcp: tuple[TestClient, FakeVerifier],
) -> None:
    client, _ = mcp
    response = rpc(client, "tools/list")
    assert response.status_code == 401
    assert "resource_metadata" in response.headers["www-authenticate"]


def test_an_invalid_token_is_rejected(mcp: tuple[TestClient, FakeVerifier]) -> None:
    client, _ = mcp
    assert rpc(client, "tools/list", token="not-a-real-token").status_code == 401


def test_oauth_discovery_points_clients_at_the_identity_provider(
    mcp: tuple[TestClient, FakeVerifier],
) -> None:
    client, _ = mcp
    metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["authorization_servers"] == ["http://idp.test/realms/resolve"]
    assert metadata["resource"].endswith("/mcp")


def test_an_authenticated_client_sees_all_tools_with_clean_schemas(
    mcp: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = mcp
    token = verifier.add("ann")
    tools = body(rpc(client, "tools/list", token=token))["result"]["tools"]
    assert {t["name"] for t in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert "ctx" not in tool["inputSchema"].get("properties", {})
    create = next(t for t in tools if t["name"] == "create_ticket")
    assert create["annotations"]["readOnlyHint"] is False
    assert all(
        t["annotations"]["readOnlyHint"] for t in tools if t["name"] != "create_ticket"
    )


def test_a_member_can_call_tools_and_sees_only_their_journals(
    mcp: tuple[TestClient, FakeVerifier], session: Session
) -> None:
    client, verifier = mcp
    mine, other = make_journal(session, "JA"), make_journal(session, "JB")
    ann = make_user(session, "ann")
    add_member(session, mine, ann, Role.VIEWER)
    del other
    result = call(client, verifier.add("ann"), "list_journals")
    assert result.get("isError") is not True
    assert result["structuredContent"]["journals"] == [
        {"code": "JA", "name": "Journal JA", "your_role": "viewer"}
    ]


def test_errors_are_reported_to_the_client_without_internals(
    mcp: tuple[TestClient, FakeVerifier], session: Session
) -> None:
    client, verifier = mcp
    make_journal(session, "JA")
    result = call(client, verifier.add("stranger"), "list_tickets", journal="JA")
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "not found" in text and "Traceback" not in text and "sql" not in text.lower()


def test_writing_needs_confirmation_over_the_wire_too(
    mcp: tuple[TestClient, FakeVerifier], session: Session
) -> None:
    client, verifier = mcp
    journal = make_journal(session, "JA")
    add_member(session, journal, make_user(session, "ann"), Role.VIEWER)
    token = verifier.add("ann")

    preview = call(
        client,
        token,
        "create_ticket",
        journal="JA",
        title="Please check the figure rules",
    )
    assert preview["structuredContent"]["status"] == "confirmation_required"
    assert session.exec(select(func.count()).select_from(Ticket)).one() == 0

    created = call(
        client,
        token,
        "create_ticket",
        journal="JA",
        title="Please check the figure rules",
        confirm=True,
    )
    assert created["structuredContent"]["status"] == "created"
    assert session.exec(select(func.count()).select_from(Ticket)).one() == 1


def test_invalid_arguments_are_rejected_before_any_work(
    mcp: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = mcp
    result = call(
        client, verifier.add("ann"), "list_tickets", journal="JA", status="everything"
    )
    assert result["isError"] is True


def test_prompts_and_resource_templates_are_listed(
    mcp: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = mcp
    token = verifier.add("ann")
    prompts = body(rpc(client, "prompts/list", token=token))["result"]["prompts"]
    templates = body(rpc(client, "resources/templates/list", token=token))["result"][
        "resourceTemplates"
    ]
    assert {p["name"] for p in prompts} == {"triage_open_tickets", "prepare_reply"}
    assert [t["uriTemplate"] for t in templates] == ["journal://{code}/stylesheet"]
