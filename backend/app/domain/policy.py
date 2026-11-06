"""Role-based access rules.

This module is the single source of truth for who may do what. It is pure
(no I/O) so the whole matrix can be unit-tested exhaustively.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """Role a user holds inside one journal."""

    LEAD = "lead"
    ASSISTANT = "assistant"
    VIEWER = "viewer"


class Action(StrEnum):
    """Operations that are subject to authorization."""

    MANAGE_JOURNAL = "manage_journal"
    UPLOAD_STYLESHEET = "upload_stylesheet"
    UPLOAD_CONTENT = "upload_content"
    CREATE_TICKET = "create_ticket"
    WORK_TICKETS = "work_tickets"
    APPROVE_RESOLUTION = "approve_resolution"
    ASK = "ask"
    READ = "read"


_VIEWER = frozenset({Action.ASK, Action.READ, Action.CREATE_TICKET})
_ASSISTANT = _VIEWER | {Action.UPLOAD_CONTENT, Action.WORK_TICKETS}
_LEAD = _ASSISTANT | {Action.UPLOAD_STYLESHEET, Action.APPROVE_RESOLUTION}

_GRANTS: Mapping[Role, frozenset[Action]] = {
    Role.VIEWER: _VIEWER,
    Role.ASSISTANT: frozenset(_ASSISTANT),
    Role.LEAD: frozenset(_LEAD),
}


def role_can(role: Role, action: Action) -> bool:
    """Returns whether a journal role grants `action`."""
    return action in _GRANTS[role]


@dataclass(frozen=True)
class Scope:
    """What a single user may touch; built once per request.

    Attributes:
        is_admin: Global administrator; may do anything in every journal.
        journal_roles: The user's role in each journal they belong to.
    """

    is_admin: bool = False
    journal_roles: Mapping[uuid.UUID, Role] = field(default_factory=dict)

    def allows(self, journal_id: uuid.UUID, action: Action) -> bool:
        """Returns whether the user may perform `action` in `journal_id`."""
        if self.is_admin:
            return True
        role = self.journal_roles.get(journal_id)
        return role is not None and role_can(role, action)

    @property
    def journal_ids(self) -> frozenset[uuid.UUID]:
        """Journals the user is a member of (admins see all via `is_admin`)."""
        return frozenset(self.journal_roles)
