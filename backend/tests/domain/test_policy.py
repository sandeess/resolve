import uuid

import pytest

from app.domain.policy import Action, Role, Scope, role_can

A = Action

# role -> actions it must have. Everything else must be denied.
EXPECTED: dict[Role, set[Action]] = {
    Role.VIEWER: {A.ASK, A.READ, A.CREATE_TICKET},
    Role.ASSISTANT: {A.ASK, A.READ, A.CREATE_TICKET, A.UPLOAD_CONTENT, A.WORK_TICKETS},
    Role.LEAD: {
        A.ASK,
        A.READ,
        A.CREATE_TICKET,
        A.UPLOAD_CONTENT,
        A.WORK_TICKETS,
        A.UPLOAD_STYLESHEET,
        A.APPROVE_RESOLUTION,
    },
}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("action", list(Action))
def test_role_matrix(role: Role, action: Action) -> None:
    assert role_can(role, action) is (action in EXPECTED[role])


def test_nobody_but_admin_manages_journals() -> None:
    assert not any(role_can(role, A.MANAGE_JOURNAL) for role in Role)
    assert Scope(is_admin=True).allows(uuid.uuid4(), A.MANAGE_JOURNAL)


def test_scope_is_per_journal() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    scope = Scope(journal_roles={mine: Role.LEAD})
    assert scope.allows(mine, A.UPLOAD_STYLESHEET)
    assert not scope.allows(other, A.READ)
    assert scope.journal_ids == {mine}
