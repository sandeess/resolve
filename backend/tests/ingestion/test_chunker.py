import pytest

from app.ingestion.chunker import chunk_sections
from app.ingestion.parsers import Section


def test_small_section_is_one_chunk() -> None:
    chunks = chunk_sections([Section("one\n\ntwo", "A")], max_chars=100, overlap=10)
    assert [(c.text, c.locator) for c in chunks] == [("one\n\ntwo", "A")]


def test_paragraphs_are_packed_up_to_limit() -> None:
    text = "\n\n".join(["x" * 40] * 5)
    chunks = chunk_sections([Section(text, "A")], max_chars=100, overlap=10)
    assert [len(c.text) for c in chunks] == [82, 82, 40]


def test_chunks_never_span_sections() -> None:
    chunks = chunk_sections(
        [Section("a", "S1"), Section("b", "S2")], max_chars=100, overlap=10
    )
    assert [(c.text, c.locator) for c in chunks] == [("a", "S1"), ("b", "S2")]


def test_long_paragraph_is_cut_with_overlap_and_loses_nothing() -> None:
    words = [f"w{i}" for i in range(400)]
    chunks = chunk_sections([Section(" ".join(words), "A")], max_chars=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)
    seen = {w for c in chunks for w in c.text.split()}
    assert seen == set(words)
    assert set(chunks[0].text.split()[-3:]) & set(chunks[1].text.split())  # overlap


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk_sections([Section("a", "A")], max_chars=10, overlap=10)
