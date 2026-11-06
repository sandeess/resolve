"""Split parsed sections into passages sized for embedding and citation."""

import re
from dataclasses import dataclass

from app.ingestion.parsers import Section

DEFAULT_MAX_CHARS = 1800
DEFAULT_OVERLAP = 200


@dataclass(frozen=True)
class TextChunk:
    text: str
    locator: str


def chunk_sections(
    sections: list[Section],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """Packs paragraphs into chunks of at most `max_chars`.

    Chunks never span sections (so a locator always points at one place).
    Overlap is only used when a single paragraph is too long and must be cut.
    """
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    chunks: list[TextChunk] = []
    for section in sections:
        current = ""
        for paragraph in _paragraphs(section.text):
            for piece in _cut(paragraph, max_chars, overlap):
                if current and len(current) + 2 + len(piece) > max_chars:
                    chunks.append(TextChunk(current, section.locator))
                    current = piece
                else:
                    current = f"{current}\n\n{piece}" if current else piece
        if current:
            chunks.append(TextChunk(current, section.locator))
    return chunks


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _cut(paragraph: str, max_chars: int, overlap: int) -> list[str]:
    """Splits one over-long paragraph on whitespace with overlap."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        if end < len(paragraph):
            space = paragraph.rfind(" ", start + max_chars // 2, end)
            end = space if space > start else end
        pieces.append(paragraph[start:end].strip())
        if end >= len(paragraph):
            break
        start = max(end - overlap, start + 1)
    return pieces
