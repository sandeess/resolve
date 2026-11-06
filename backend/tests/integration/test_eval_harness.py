"""Mechanics of the eval harness, using deterministic fakes (no network)."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from corpus import build_corpus
from harness import CONFIGS, end_to_end, reset, retrieval_ablation, summarise
from sqlalchemy import Engine

from tests.integration.conftest import FakeEmbedder, ScriptedChat


@pytest.fixture(autouse=True)
def _empty_database_afterwards(engine: Engine) -> Iterator[None]:
    """The harness seeds through the engine directly, so wipe what it leaves."""
    yield
    reset(engine)


def test_ablation_runs_every_configuration_and_finds_lexical_matches(
    engine: Engine, tmp_path: Path
) -> None:
    corpus = build_corpus(seed=3, n_journals=1)
    rows, _ = retrieval_ablation(
        engine, corpus, FakeEmbedder(), tmp_path, log=lambda _m: None
    )

    assert [r.config for r in rows] == [c.name for c in CONFIGS]
    assert all(0 <= r.recall_5 <= 1 and 0 <= r.mrr <= 1 for r in rows)
    keyword = rows[0]
    assert keyword.lexical_recall_5 > 0.5  # shared words are enough for full-text
    vector = next(r for r in rows if r.config == "vector only, with context prefix")
    default = next(r for r in rows if "(default)" in r.config)
    # Regression guard for the tuning: the default hybrid must not fall materially
    # below vector-only, which equal-weight fusion once did.
    assert default.recall_5 >= vector.recall_5 - 0.1


def test_end_to_end_scores_refusals_and_flags_wrong_answers(
    engine: Engine, tmp_path: Path
) -> None:
    corpus = build_corpus(seed=3, n_journals=1)
    embedder = FakeEmbedder()
    _, seeded = retrieval_ablation(
        engine, corpus, embedder, tmp_path, log=lambda _m: None
    )

    refuses = ScriptedChat(json.dumps({"sufficient": False}))
    outcomes = end_to_end(
        engine, corpus, seeded, embedder, refuses, workers=2, log=lambda _m: None
    )
    summary = summarise(outcomes)

    assert summary.n == len(corpus.golden) and summary.error_count == 0
    assert summary.abstention_recall == 1.0  # a model that always refuses never leaks
    assert summary.answerable_pass_rate == 0.0 and summary.false_abstention_rate == 1.0
    assert summary.forbidden_leak_rate == 0.0
    assert set(summary.by_type) == {i.type for i in corpus.golden}
