"""Builds the eval database from the synthetic corpus and measures the system.

Everything runs through the real services (upload, ingestion, tickets,
retrieval, Ask), so the numbers describe the product, not a re-implementation.
"""

import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from alembic import command
from alembic.config import Config
from corpus import Corpus, GoldenItem
from metrics import (
    contains,
    contains_in_order,
    first_relevant_rank,
    mean_reciprocal_rank,
    percentile,
    rate,
    recall_at_k,
)
from sqlalchemy import Engine, text
from sqlmodel import Session, col, create_engine, select

from app.domain.enums import DocumentKind, TicketPriority, TicketSource
from app.domain.policy import Scope
from app.llm.base import ChatModel, Embedder
from app.models import Article, Chunk, Journal, TicketCreate, User
from app.rag.ask import AskResult, ask
from app.rag.retrieval import KEYWORD_WEIGHT, SearchMode, hybrid_search
from app.services import documents, ingestion, tickets
from app.storage.local import LocalStorage

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
ADMIN = Scope(is_admin=True)


class CachedEmbedder:
    """Wraps an embedder with an on-disk cache so reruns are free and exact."""

    def __init__(self, inner: Embedder, path: Path) -> None:
        self._inner, self._path, self._lock = inner, path, threading.Lock()
        self._cache: dict[str, list[float]] = (
            json.loads(path.read_text()) if path.exists() else {}
        )
        self.hits = self.misses = 0

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    def _key(self, text_: str) -> str:
        return hashlib.sha256(f"{self.model_name}\x00{text_}".encode()).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            missing = [
                t for t in dict.fromkeys(texts) if self._key(t) not in self._cache
            ]
        if missing:
            vectors = self._inner.embed(missing)
            with self._lock:
                for t, v in zip(missing, vectors, strict=True):
                    self._cache[self._key(t)] = v
                self.misses += len(missing)
        with self._lock:
            self.hits += len(texts) - len(missing)
            return [self._cache[self._key(t)] for t in texts]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._path.write_text(json.dumps(self._cache))


@contextmanager
def eval_database(dsn: str | None = None) -> Iterator[Engine]:
    """A migrated, throwaway pgvector database (a container unless `dsn` is given)."""
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

    def migrate(url: str) -> None:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
        cfg.attributes["url"] = url
        command.upgrade(cfg, "head")

    if dsn:
        migrate(dsn)
        engine = create_engine(dsn)
        yield engine
        engine.dispose()
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg18", driver="psycopg") as pg:
        url = pg.get_connection_url()
        migrate(url)
        engine = create_engine(url)
        yield engine
        engine.dispose()


@dataclass
class Seeded:
    journal_ids: dict[str, uuid.UUID]
    article_ids: dict[str, uuid.UUID]  # manuscript id -> article id


def reset(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE ticketresolution, ticketmessage, ticket, chunk, documentversion, document, article, journalmember, journal, app_user CASCADE"
            )
        )


@contextmanager
def embedding_prefix(enabled: bool) -> Iterator[None]:
    """Ablation switch: embed raw passages instead of "name - section\\n passage"."""
    if enabled:
        yield
        return
    originals = (ingestion.embedding_text, tickets.embedding_text)

    def plain(_name: str, _locator: str, content: str) -> str:
        return content

    ingestion.embedding_text = plain
    tickets.embedding_text = plain
    try:
        yield
    finally:
        ingestion.embedding_text, tickets.embedding_text = originals


def seed(
    engine: Engine, corpus: Corpus, embedder: Embedder, storage_dir: Path
) -> Seeded:
    """Loads journals, every document version (indexed), and tickets."""
    storage = LocalStorage(storage_dir)
    journal_ids: dict[str, uuid.UUID] = {}
    article_ids: dict[str, uuid.UUID] = {}
    with Session(engine) as session:
        admin = User(sub="eval-admin", email="eval@example.com", is_admin=True)
        session.add(admin)
        for code in corpus.journals:
            journal = Journal(code=code, name=f"Journal {code}")
            session.add(journal)
            session.flush()
            journal_ids[code] = journal.id
            for manuscript in corpus.manuscripts[code]:
                article = Article(
                    journal_id=journal.id,
                    manuscript_id=manuscript,
                    title=f"Paper {manuscript}",
                )
                session.add(article)
                session.flush()
                article_ids[manuscript] = article.id
        session.commit()
        session.refresh(admin)

        for doc in corpus.docs:
            for body in doc.versions:  # v1 then v2: v1 stays in the index as stale
                version = documents.upload_version(
                    session,
                    storage,
                    ADMIN,
                    admin,
                    journal_id=journal_ids[doc.journal],
                    article_id=article_ids[doc.manuscript] if doc.manuscript else None,
                    kind=DocumentKind(doc.kind),
                    name=doc.name,
                    content_type=doc.content_type,
                    data=body.encode(),
                    max_bytes=1_000_000,
                )
                ingestion.ingest_version(session, storage, embedder, version.id)

        for spec in corpus.tickets:
            ticket = tickets.create_ticket(
                session,
                ADMIN,
                admin,
                journal_ids[spec.journal],
                TicketCreate(
                    title=spec.title,
                    priority=TicketPriority.NORMAL,
                    source=TicketSource.WEB,
                ),
            )
            tickets.resolve_ticket(
                session,
                ADMIN,
                admin,
                embedder,
                ticket.id,
                answer=spec.answer,
                approve=spec.approve,
            )
    return Seeded(journal_ids, article_ids)


# --- retrieval ablation -------------------------------------------------------


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    mode: SearchMode
    prefix: bool
    text_weight: float = 1.0


def _build_configs() -> tuple[RetrievalConfig, ...]:
    """Ablation set. The production default is whichever matches KEYWORD_WEIGHT."""
    weights = sorted({1.0, 0.5, 0.3, 0.15, 0.08, 0.04, KEYWORD_WEIGHT}, reverse=True)

    def hybrid(prefix: bool, weight: float) -> RetrievalConfig:
        is_default = prefix and weight == KEYWORD_WEIGHT
        label = "with context prefix" if prefix else "raw passages"
        suffix = " (default)" if is_default else ""
        return RetrievalConfig(
            f"hybrid, {label}, keyword weight {weight:g}{suffix}",
            "hybrid",
            prefix,
            weight,
        )

    return (
        RetrievalConfig("keyword only (full-text)", "text", True),
        RetrievalConfig("vector only, raw passages", "vector", False),
        RetrievalConfig("vector only, with context prefix", "vector", True),
        hybrid(False, KEYWORD_WEIGHT),
        *(hybrid(True, w) for w in weights),
    )


CONFIGS = _build_configs()


@dataclass
class RetrievalRow:
    config: str
    n: int
    recall_1: float
    recall_3: float
    recall_5: float
    mrr: float
    paraphrase_recall_5: float
    lexical_recall_5: float


def _answerable(corpus: Corpus) -> list[GoldenItem]:
    return [i for i in corpus.golden if i.evidence is not None and not i.expect_abstain]


def _rank_item(
    session: Session,
    item: GoldenItem,
    seeded: Seeded,
    embedder: Embedder,
    cfg: RetrievalConfig,
    k: int,
) -> int | None:
    assert item.evidence is not None
    hits = hybrid_search(
        session,
        ADMIN,
        journal_id=seeded.journal_ids[item.journal],
        query=item.question,
        query_vector=embedder.embed([item.question])[0],
        article_id=seeded.article_ids[item.manuscript] if item.manuscript else None,
        top_k=k,
        mode=cfg.mode,
        text_weight=cfg.text_weight,
    )
    return first_relevant_rank([h.content for h in hits], item.evidence)


def retrieval_ablation(
    engine: Engine,
    corpus: Corpus,
    embedder: Embedder,
    storage_root: Path,
    *,
    k: int = 10,
    log: Callable[[str], None] = print,
) -> tuple[list[RetrievalRow], Seeded]:
    """Measures every config. The last state left in the database is the default one."""
    items = _answerable(corpus)
    rows: list[RetrievalRow] = []
    # Seed once per prefix setting; the default (prefix on) goes last so Ask can reuse it.
    seeded: Seeded | None = None
    for prefix in (False, True):
        reset(engine)
        log(f"  indexing corpus (context prefix {'on' if prefix else 'off'})")
        with embedding_prefix(prefix):
            seeded = seed(engine, corpus, embedder, storage_root / f"p{int(prefix)}")
        with Session(engine) as session:
            for cfg in (c for c in CONFIGS if c.prefix == prefix):
                ranks = {
                    i.id: _rank_item(session, i, seeded, embedder, cfg, k)
                    for i in items
                }
                para = [ranks[i.id] for i in items if i.style == "paraphrase"]
                lex = [ranks[i.id] for i in items if i.style == "lexical"]
                everything = list(ranks.values())
                rows.append(
                    RetrievalRow(
                        cfg.name,
                        len(items),
                        recall_at_k(everything, 1),
                        recall_at_k(everything, 3),
                        recall_at_k(everything, 5),
                        mean_reciprocal_rank(everything),
                        recall_at_k(para, 5),
                        recall_at_k(lex, 5),
                    )
                )
    assert seeded is not None
    order = {c.name: n for n, c in enumerate(CONFIGS)}
    return sorted(rows, key=lambda r: order[r.config]), seeded


# --- end to end ---------------------------------------------------------------


@dataclass
class ItemOutcome:
    id: str
    type: str
    style: str
    question: str
    expect_abstain: bool
    abstained: bool
    answer: str
    answer_ok: bool
    forbidden_hit: list[str]
    cites_evidence: bool
    passed: bool
    seconds: float
    error: str | None = None
    cited: list[str] = field(default_factory=list)


def _judge(
    item: GoldenItem, result: AskResult, cited_texts: list[str], seconds: float
) -> ItemOutcome:
    forbidden_hit = [f for f in item.forbidden if contains(result.answer, f)]
    if item.expect_abstain:
        ok, cites = result.abstained, True
        passed = result.abstained and not forbidden_hit
    else:
        ok = not result.abstained and all(
            contains_in_order(result.answer, e) for e in item.expected_contains
        )
        cites = bool(item.evidence) and any(
            contains(t, item.evidence or "") for t in cited_texts
        )
        passed = ok and cites and not forbidden_hit
    return ItemOutcome(
        item.id,
        item.type,
        item.style,
        item.question,
        item.expect_abstain,
        result.abstained,
        result.answer,
        ok,
        forbidden_hit,
        cites,
        passed,
        seconds,
        cited=[
            f"{c.source_name}{f' v{c.version_no}' if c.version_no else ''}"
            for c in result.citations
        ],
    )


def end_to_end(
    engine: Engine,
    corpus: Corpus,
    seeded: Seeded,
    embedder: Embedder,
    chat: ChatModel,
    *,
    limit: int | None = None,
    workers: int = 4,
    log: Callable[[str], None] = print,
) -> list[ItemOutcome]:
    """Runs the real Ask flow (retrieve, generate, verify) for every golden item."""
    items = corpus.golden[:limit] if limit else corpus.golden

    def run(item: GoldenItem) -> ItemOutcome:
        started = time.perf_counter()
        try:
            with Session(engine) as session:
                result = ask(
                    session=session,
                    scope=ADMIN,
                    embedder=embedder,
                    chat=chat,
                    journal_id=seeded.journal_ids[item.journal],
                    question=item.question,
                    article_id=seeded.article_ids[item.manuscript]
                    if item.manuscript
                    else None,
                    use_cache=False,  # measure the real pipeline, not the cache
                )
                chunk_ids = [c.chunk_id for c in result.citations]
                cited_texts = (
                    [
                        c.content
                        for c in session.exec(
                            select(Chunk).where(col(Chunk.id).in_(chunk_ids))
                        )
                    ]
                    if chunk_ids
                    else []
                )
        except Exception as exc:  # one flaky call must not sink the whole run
            return ItemOutcome(
                item.id,
                item.type,
                item.style,
                item.question,
                item.expect_abstain,
                False,
                "",
                False,
                [],
                False,
                False,
                time.perf_counter() - started,
                error=repr(exc),
            )
        return _judge(item, result, cited_texts, time.perf_counter() - started)

    with ThreadPoolExecutor(workers) as pool:
        outcomes = []
        for n, outcome in enumerate(pool.map(run, items), start=1):
            outcomes.append(outcome)
            if n % 20 == 0:
                log(f"  answered {n}/{len(items)}")
    return outcomes


@dataclass
class E2ESummary:
    n: int
    pass_rate: float
    answerable_pass_rate: float
    false_abstention_rate: float
    abstention_recall: float
    forbidden_leak_rate: float
    citation_rate: float
    error_count: int
    p50_seconds: float
    p95_seconds: float
    by_type: dict[str, tuple[int, float]]


def summarise(outcomes: list[ItemOutcome]) -> E2ESummary:
    answerable = [o for o in outcomes if not o.expect_abstain]
    should_abstain = [o for o in outcomes if o.expect_abstain]
    by_type: dict[str, list[bool]] = {}
    for o in outcomes:
        by_type.setdefault(o.type, []).append(o.passed)
    return E2ESummary(
        n=len(outcomes),
        pass_rate=rate([o.passed for o in outcomes]),
        answerable_pass_rate=rate([o.passed for o in answerable]),
        false_abstention_rate=rate([o.abstained for o in answerable]),
        abstention_recall=rate([o.abstained for o in should_abstain]),
        forbidden_leak_rate=rate([bool(o.forbidden_hit) for o in outcomes]),
        citation_rate=rate([o.cites_evidence for o in answerable if not o.abstained]),
        error_count=sum(1 for o in outcomes if o.error),
        p50_seconds=percentile((o.seconds for o in outcomes), 50),
        p95_seconds=percentile((o.seconds for o in outcomes), 95),
        by_type={t: (len(v), rate(v)) for t, v in sorted(by_type.items())},
    )
