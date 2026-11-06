from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core import rls
from app.core.config import settings
from app.core.db import engine
from app.core.providers import (
    get_chat_model,
    get_embedder,
    get_storage,
    get_verifier,
)
from app.core.security import OidcVerifier, TokenError
from app.domain.policy import Scope
from app.llm.base import ChatModel, Embedder
from app.models import User
from app.services import access
from app.storage.base import Storage

bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session]:
    """One session per request, under row-level security from the first query.

    Until the caller is authenticated the context is anonymous (sees no rows);
    `get_current_user` then binds the real identity.
    """
    with Session(engine) as session:
        rls.bind(session, rls.RlsContext())
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


StorageDep = Annotated[Storage, Depends(get_storage)]


EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
ChatModelDep = Annotated[ChatModel, Depends(get_chat_model)]


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[OidcVerifier, Depends(get_verifier)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = verifier.verify(credentials.credentials)
    except TokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = access.provision_user(session, claims, admin_role=settings.OIDC_ADMIN_ROLE)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    rls.bind(session, rls.RlsContext(user.id, user.is_admin))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_scope(session: SessionDep, user: CurrentUser) -> Scope:
    return access.build_scope(session, user)


ScopeDep = Annotated[Scope, Depends(get_scope)]
