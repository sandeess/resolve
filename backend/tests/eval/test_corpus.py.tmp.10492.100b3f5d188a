import json

import pytest
from corpus import FACTS, UNANSWERABLE, Corpus, build_corpus
from metrics import contains


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return build_corpus(seed=7, n_journals=3)


def _current_texts(corpus: Corpus, journal: str, manuscript: str | None) -> list[str]:
    """Texts the system treats as live for a question: latest versions only."""
    texts = [
        d.versions[-1]
        for d in corpus.docs
        if d.journal == journal and d.manuscript in (None, manuscript)
    ]
    texts += [t.answer for t in corpus.tickets if t.journal == journal and t.approve]
    return texts


def test_generation_is_deterministic_and_seed_sensitive() -> None:
    assert build_corpus(7).golden_jsonl() == build_corpus(7).golden_jsonl()
    assert build_corpus(7).golden_jsonl() != build_corpus(8).golden_jsonl()


def test_golden_jsonl_round_trips(corpus: Corpus) -> None:
    rows = [json.loads(line) for line in corpus.golden_jsonl().splitlines()]
    assert len(rows) == len(corpus.golden) and len({r["id"] for r in rows}) == len(rows)


def test_every_answerable_question_has_live_evidence(corpus: Corpus) -> None:
    for item in corpus.golden:
        if item.expect_abstain:
            continue
        assert item.evidence and item.expected_contains
        live = _current_texts(corpus, item.journal, item.manuscript)
        assert any(contains(t, item.evidence) for t in live), item.id


def test_expected_values_are_inside_their_evidence(corpus: Corpus) -> None:
    for item in corpus.golden:
        for value in item.expected_contains:
            assert contains(item.evidence or "", value), item.id


def test_forbidden_values_never_overlap_the_expected_answer(corpus: Corpus) -> None:
    for item in corpus.golden:
        for bad in item.forbidden:
            assert not any(
                contains(v, bad) or contains(bad, v) for v in item.expected_contains
            ), item.id


def test_stale_questions_forbid_the_old_value_which_only_v1_contains(
    corpus: Corpus,
) -> None:
    stale = [i for i in corpus.golden if i.type == "stale"]
    assert len(stale) >= 3 * 6  # six changed rules per journal
    for item in stale:
        docs = [
            d
            for d in corpus.docs
            if d.journal == item.journal
            and d.manuscript is None
            and len(d.versions) == 2
        ]
        old_text = " ".join(d.versions[0] for d in docs)
        new_text = " ".join(d.versions[1] for d in docs)
        assert any(contains(old_text, f) for f in item.forbidden), item.id
        assert contains(new_text, item.evidence or ""), item.id


def test_traps_are_present_and_well_formed(corpus: Corpus) -> None:
    kinds = {i.type for i in corpus.golden}
    assert kinds == {
        "fact",
        "stale",
        "article",
        "article_isolation",
        "ticket",
        "unapproved_trap",
        "unanswerable",
    }
    unapproved = [t for t in corpus.tickets if not t.approve]
    assert len(unapproved) == 3 and all(contains(t.answer, "50%") for t in unapproved)
    assert sum(1 for i in corpus.golden if i.type == "unanswerable") == 3 * len(
        UNANSWERABLE
    )
    assert all(
        i.expect_abstain and not i.evidence
        for i in corpus.golden
        if i.type in ("unanswerable", "unapproved_trap")
    )


def test_paraphrases_avoid_the_answer_sentences_keywords() -> None:
    """The paraphrase set is only a semantic test if it shares few content words."""
    stop = {
        "the",
        "a",
        "an",
        "of",
        "to",
        "do",
        "how",
        "what",
        "which",
        "is",
        "are",
        "in",
        "be",
        "i",
        "my",
        "we",
        "you",
        "for",
        "it",
        "can",
        "should",
        "must",
        "does",
    }

    def words(sentence: str) -> set[str]:
        return {w.strip("?.,'").lower() for w in sentence.split()} - stop

    overlaps = []
    for fact in FACTS:
        overlaps.append(
            len(words(fact.paraphrase) & words(fact.sentence))
            / max(1, len(words(fact.paraphrase)))
        )
    assert sum(overlaps) / len(overlaps) < 0.2
