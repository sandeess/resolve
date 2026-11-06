"""Who is calling an MCP tool, and the database session to act as them.

MCP clients are third-party programs acting for a user, so they are held to
member-level access: an MCP session is **never** an admin, even for a user who is
one in the web app. Row-level security is bound to the same restricted identity,
so the database enforces it as well as the services.
"""

import dataclasses
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlmodel import Session

from app.core import rls
from app.core.config import settings
from app.core.db import engine
from app.core.security import TokenClaims
from app.domain.errors import PermissionDeniedError
from app.domain.policy import Scope
from app.models import User
from app.services import access


@dataclass(frozen=True)
class McpContext:
    session: Session
    user: User
    scope: Scope
    client_id: str | None


@contextmanager
def open_context(claims: TokenClaims) -> Iterator[McpContext]:
    """A session bound to the token's user, with admin rights stripped."""
    with Session(engine) as session:
        rls.bind(session, rls.RlsContext())
        user = access.provision_user(
            session, claims, admin_role=settings.OIDC_ADMIN_ROLE
        )
        if not user.is_active:
            raise PermissionDeniedError("this account is disabled")
        rls.bind(session, rls.RlsContext(user.id, is_admin=False))
        scope = dataclasses.replace(access.build_scope(session, user), is_admin=False)
        yield McpContext(session, user, scope, claims.client_id)
