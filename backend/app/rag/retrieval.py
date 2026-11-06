"""Scoped hybrid retrieval: vector similarity + full-text, fused with RRF.

Every query is restricted to one journal the caller may ask in, to knowledge
that is *live* (current document versions, and closed tickets, whose chunks
exist only while approved), and to the chosen article plus journal-level
material. Those filters run in SQL before ranking, so stale or foreign passages
can never be returned, however well they match.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import ColumnElement, func, or_
from sqlmodel import Session, col, select

from app.domain.policy import Action, Scope
from app.models import Chunk, Document, DocumentVersion, Ticket
from app.services.access import require

RRF_K = 60  # standard reciprocal-rank-fusion damping constant
# How much the keyword ranker counts relative to the vector ranker (1.0 = equal).
# At 1.0, noisy keyword matches pushed correct passages down on paraphrased questions
# (recall@5 89.9% vs 97.8% for vector alone). 0.04 matched vector-only recall on two
# seeded corpora while keeping the keyword signal as a tie-breaker for exact terms,
# which the synthetic corpus does not exercise. See eval/README.md before changing.
KEYWORD_WEIGHT = 0.04

SourceType = Literal["document", "ticket"]
SearchMode = Literal["hybrid", "vector", "text"]


@dataclass(frozen=True)
class Hit:
    chunk_id: uuid.UUID
    source_type: SourceType
    source_name: str  # document name, or "T-12" for a ticket
    locator: str
    content: str
    score: float
    article_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    version_no: int | None = None
    ticket_id: uuid.UUID | None = None
    ticket_number: int | None = None
    dated: str | None = (
        None  # ISO timestamp (to the minute) of the ticket or document version
    )


def hybrid_search(
    session: Session,
    scope: Scope,
    *,
    journal_id: uuid.UUID,
    query: str,
    query_vector: list[float],
    article_id: uuid.UUID | None = None,
    top_k: int = 6,
    pool: int = 30,
    mode: SearchMode = "hybrid",
    text_weight: float = KEYWORD_WEIGHT,
) -> list[Hit]:
    """Returns the best `top_k` chunks for `query` the caller may see.

    `mode` and `text_weight` exist so evaluations can ablate and tune the two
    rankers; production uses the defaults (hybrid, `KEYWORD_WEIGHT`).

    Raises:
        PermissionDeniedError: The caller may not ask in this journal.
    """
    require(scope, journal_id, Action.ASK)
    allowed = _allowed(journal_id, article_id)

    by_vector = (
        []
        if mode == "text"
        else session.exec(
            select(col(Chunk.id))
            .join(
                DocumentVersion,
                col(DocumentVersion.id) == col(Chunk.version_id),
                isouter=True,
            )
            .where(*allowed)
            .order_by(Chunk.embedding.cosine_distance(query_vector))  # type: ignore[attr-defined]  # pgvector comparator
            .limit(pool)
        ).all()
    )

    ts_query = func.websearch_to_tsquery("english", _any_word_query(query))
    by_text = (
        []
        if mode == "vector"
        else session.exec(
            select(col(Chunk.id))
            .join(
                DocumentVersion,
                col(DocumentVersion.id) == col(Chunk.version_id),
                isouter=True,
            )
            .where(*allowed, col(Chunk.tsv).op("@@")(ts_query))
            .order_by(func.ts_rank_cd(col(Chunk.tsv), ts_query).desc())
            .limit(pool)
        ).all()
    )

    fused = _rrf([list(by_vector), list(by_text)], [1.0, text_weight])
    top = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
    if not top:
        return []

    rows = session.exec(
        select(Chunk, DocumentVersion, Document, Ticket)
        .join(
            DocumentVersion,
            col(DocumentVersion.id) == col(Chunk.version_id),
            isouter=True,
        )
        .join(
            Document, col(Document.id) == col(DocumentVersion.document_id), isouter=True
        )
        .join(Ticket, col(Ticket.id) == col(Chunk.ticket_id), isouter=True)
        .where(col(Chunk.id).in_([chunk_id for chunk_id, _ in top]))
    ).all()
    by_id = {
        chunk.id: (chunk, version, doc, ticket) for chunk, version, doc, ticket in rows
    }
    return [_hit(*by_id[chunk_id], score) for chunk_id, score in top]


def _hit(
    chunk: Chunk,
    version: DocumentVersion | None,
    document: Document | None,
    ticket: Ticket | None,
    score: float,
) -> Hit:
    if ticket is not None:
        return Hit(
            chunk_id=chunk.id,
            source_type="ticket",
            source_name=f"T-{ticket.number}",
            locator=chunk.locator,
            content=chunk.content,
            score=score,
            article_id=chunk.article_id,
            ticket_id=ticket.id,
            ticket_number=ticket.number,
            dated=ticket.created_at.isoformat(timespec="minutes"),
        )
    assert version is not None and document is not None
    return Hit(
        chunk_id=chunk.id,
        source_type="document",
        source_name=document.name,
        locator=chunk.locator,
        content=chunk.content,
        score=score,
        article_id=chunk.article_id,
        document_id=document.id,
        version_id=version.id,
        version_no=version.version_no,
        dated=version.created_at.isoformat(timespec="minutes"),
    )


def _allowed(
    journal_id: uuid.UUID, article_id: uuid.UUID | None
) -> list[ColumnElement[bool]]:
    article_filter = (
        or_(col(Chunk.article_id) == article_id, col(Chunk.article_id).is_(None))
        if article_id is not None
        else col(Chunk.article_id).is_(None)
    )
    return [
        col(Chunk.journal_id) == journal_id,
        # Documents: only the current version. Tickets: chunks exist only while approved.
        or_(
            col(DocumentVersion.is_current).is_(True),
            col(Chunk.ticket_id).is_not(None),
        ),
        article_filter,
    ]


def _any_word_query(question: str) -> str:
    """Turns a question into an "any of these words" full-text query.

    `plainto_tsquery` requires *every* word to appear, so a natural-language
    question like "What file format must figures be supplied as?" matches
    nothing when the passage says "Figures must be supplied as TIFF files".
    Matching any word and letting `ts_rank_cd` favour passages that share more
    of them recovers those passages. Stop words are dropped by the "english"
    configuration, and `websearch_to_tsquery` never raises on odd input.
    """
    words = dict.fromkeys(re.findall(r"[a-z0-9]+", question.lower()))
    return " or ".join(words)


def _rrf(
    rankings: list[list[uuid.UUID]], weights: list[float] | None = None
) -> dict[uuid.UUID, float]:
    """Weighted reciprocal-rank fusion: each ranker adds weight / (k + rank)."""
    weights = weights or [1.0] * len(rankings)
    scores: dict[uuid.UUID, float] = {}
    for weight, ranking in zip(weights, rankings, strict=True):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (RRF_K + rank)
    return scores
