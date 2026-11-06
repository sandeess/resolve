"""Row-level security context for request-scoped database sessions.

Postgres policies (migration 0004) decide which rows a session may see from two
transaction-local settings, `app.user_id` and `app.is_admin`. This module sets
them, and switches to the unprivileged `resolve_app` role, at the start of every
transaction of a session that carries an `RlsContext`.

This is a second line of defence: the services already check permissions, and
RLS makes a forgotten check (or a hand-written query with no journal filter)
return nothing instead of leaking another journal's rows.

Sessions without a context (the job worker, migrations, the eval harness) run
as the connection's own role and are deliberately privileged.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session as SqlaSession
from sqlalchemy.orm import SessionTransaction
from sqlmodel import Session

RLS_ROLE = "resolve_app"
_INFO_KEY = "rls"


@dataclass(frozen=True)
class RlsContext:
    """Who the policies should treat the session as. `user_id=None` sees nothing."""

    user_id: uuid.UUID | None = None
    is_admin: bool = False


def bind(session: Session, context: RlsContext) -> None:
    """Applies `context` to the current transaction (if open) and all later ones.

    A transaction may already be open when the identity becomes known (loading
    the user row opens one), so setting only the "next transaction" hook would
    leave the rest of the request running as the previous identity.
    """
    session.info[_INFO_KEY] = context
    if session.in_transaction():
        _set(session.connection(), context)


def _set(connection: Connection, context: RlsContext) -> None:
    # LOCAL: both settings end with the transaction, so a pooled connection can
    # never carry one request's identity into the next.
    connection.exec_driver_sql(f"SET LOCAL ROLE {RLS_ROLE}")
    connection.exec_driver_sql(
        "SELECT set_config('app.user_id', %s, true), set_config('app.is_admin', %s, true)",
        (
            str(context.user_id) if context.user_id else "",
            "true" if context.is_admin else "false",
        ),
    )


def _apply(
    session: SqlaSession, _txn: SessionTransaction, connection: Connection
) -> None:
    context = session.info.get(_INFO_KEY)
    if context is not None:
        _set(connection, context)


def install() -> None:
    """Registers the transaction hook once per process (idempotent)."""
    if not event.contains(SqlaSession, "after_begin", _apply):
        event.listen(SqlaSession, "after_begin", _apply)
