from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.domain.policy import Role
from tests.integration.conftest import (
    FakeVerifier,
    add_member,
    auth,
    make_journal,
    make_user,
)

API = "/api/v1"


def _put(
    client: TestClient, token: str, journal_id: object, email: str, role: str
) -> Any:
    return client.put(
        f"{API}/journals/{journal_id}/members",
        headers=auth(token),
        json={"email": email, "role": role},
    )


def test_admin_can_add_list_change_and_remove_members(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    make_user(session, "boss", admin=True)
    journal = make_journal(session, "MEM")
    colleague = make_user(session, "colleague")
    token = verifier.add("boss", admin=True)

    added = _put(client, token, journal.id, colleague.email, "assistant")
    assert added.status_code == 200
    assert added.json()["role"] == "assistant" and added.json()["pending"] is False

    changed = _put(client, token, journal.id, colleague.email.upper(), "viewer")
    assert changed.json()["role"] == "viewer"  # email match ignores case

    listed = client.get(f"{API}/journals/{journal.id}/members", headers=auth(token))
    assert [m["email"] for m in listed.json()] == [colleague.email]

    gone = client.delete(
        f"{API}/journals/{journal.id}/members/{colleague.id}", headers=auth(token)
    )
    assert gone.status_code == 204
    again = client.delete(
        f"{API}/journals/{journal.id}/members/{colleague.id}", headers=auth(token)
    )
    assert again.status_code == 404
    listed = client.get(f"{API}/journals/{journal.id}/members", headers=auth(token))
    assert listed.json() == []


def test_someone_who_has_not_signed_in_yet_is_added_as_pending_and_claims_it(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    make_user(session, "boss", admin=True)
    journal = make_journal(session, "PEN")
    admin = verifier.add("boss", admin=True)

    added = _put(client, admin, journal.id, "newhire@example.com", "assistant")
    assert added.status_code == 200 and added.json()["pending"] is True

    # Their first sign-in (token sub "newhire" -> newhire@example.com) takes it over.
    newhire = verifier.add("newhire")
    mine = client.get(f"{API}/journals", headers=auth(newhire))
    assert [j["code"] for j in mine.json()["data"]] == ["PEN"]
    assert mine.json()["data"][0]["role"] == "assistant"

    listed = client.get(f"{API}/journals/{journal.id}/members", headers=auth(admin))
    assert listed.json()[0]["pending"] is False


def test_only_administrators_manage_members(
    client: TestClient, session: Session, verifier: FakeVerifier
) -> None:
    journal = make_journal(session, "ACL")
    lead = make_user(session, "lead")
    add_member(session, journal, lead, Role.LEAD)
    token = verifier.add("lead")

    assert _put(client, token, journal.id, "x@example.com", "viewer").status_code == 403
    listing = client.get(f"{API}/journals/{journal.id}/members", headers=auth(token))
    assert listing.status_code == 403
    removal = client.delete(
        f"{API}/journals/{journal.id}/members/{lead.id}", headers=auth(token)
    )
    assert removal.status_code == 403
