import hashlib
import math
import os
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from procrastinate import testing
from sqlalchemy import Engine, text
from sqlmodel import Session, create_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

from app.api import deps  # noqa: E402
from app.core import providers  # noqa: E402
from app.core.security import TokenClaims, TokenError  # noqa: E402
from app.domain.policy import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    EMBEDDING_DIM,  # noqa: E402
    Journal,
    JournalMember,
    User,
)
from app.storage.local import LocalStorage  # noqa: E402
from app.workers.queue import queue  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def engine() -> Generator[Engine]:
    """A throwaway pgvector database migrated to head (also tests the migration)."""
    with PostgresContainer("pgvector/pgvector:pg18", driver="psycopg") as pg:
        url = pg.get_connection_url()
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
        cfg.attributes["url"] = url
        command.upgrade(cfg, "head")
        eng = create_engine(url)
        yield eng
        eng.dispose()


@pytest.fixture
def clean_db(engine: Engine) -> Generator[None]:
    """Empties every table after the test, however the data got there."""
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE documentversion, document, article, journalmember, "
                "journal, app_user CASCADE"
            )
        )


@pytest.fixture
def session(engine: Engine, clean_db: None) -> Generator[Session]:  # noqa: ARG001
    """A privileged session (owner role, RLS bypassed) for arranging test data."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "files")


class FakeEmbedder:
    """Deterministic bag-of-words embedder: shared words => similar vectors."""

    model_name = "fake-bow"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


class ScriptedChat:
    """Returns canned replies and records what it was asked."""

    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


class FakeVerifier:
    """Maps bearer tokens straight to claims: the token is the user's `sub`."""

    def __init__(self) -> None:
        self.users: dict[str, TokenClaims] = {}

    def add(self, sub: str, *, admin: bool = False) -> str:
        roles = frozenset({"resolve-admin"} if admin else ())
        self.users[sub] = TokenClaims(sub, f"{sub}@example.com", sub.title(), roles)
        return sub

    def verify(self, token: str) -> TokenClaims:
        try:
            return self.users[token]
        except KeyError:
            raise TokenError("unknown token") from None


@pytest.fixture
def verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def chat() -> ScriptedChat:
    return ScriptedChat()


@pytest.fixture
def client(
    engine: Engine,
    clean_db: None,  # noqa: ARG001
    storage: LocalStorage,
    verifier: FakeVerifier,
    embedder: FakeEmbedder,
    chat: ScriptedChat,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient]:
    # Point the real `get_db` at the test database: every API request then runs
    # in its own session under row-level security, exactly as in production.
    monkeypatch.setattr(deps, "engine", engine)
    app.dependency_overrides[providers.get_storage] = lambda: storage
    app.dependency_overrides[providers.get_verifier] = lambda: verifier
    app.dependency_overrides[providers.get_embedder] = lambda: embedder
    app.dependency_overrides[providers.get_chat_model] = lambda: chat
    with queue.replace_connector(testing.InMemoryConnector()), TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_user(session: Session, name: str, *, admin: bool = False) -> User:
    user = User(sub=name, email=f"{name}@example.com", is_admin=admin)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_journal(session: Session, code: str) -> Journal:
    journal = Journal(code=code, name=f"Journal {code}")
    session.add(journal)
    session.commit()
    session.refresh(journal)
    return journal


def add_member(session: Session, journal: Journal, user: User, role: Role) -> None:
    session.add(JournalMember(journal_id=journal.id, user_id=user.id, role=role))
    session.commit()
