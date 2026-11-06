"""Turn uploaded files into text sections that keep a human-readable locator.

Each parser returns sections (a heading path or page) rather than one blob, so
citations can say *where* in the file an answer came from. Adding a format means
adding a function to `_PARSERS`.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath

import pypdfium2 as pdfium
from docx import Document as DocxDocument


class ParseError(ValueError):
    """The file cannot be read as the format its name or type claims."""


@dataclass(frozen=True)
class Section:
    """A run of text and where it came from (e.g. "p. 3" or "Style > Dates")."""

    text: str
    locator: str


def parse(*, filename: str, content_type: str, data: bytes) -> list[Section]:
    """Parses `data` into non-empty sections.

    Raises:
        ParseError: Unsupported format, corrupt file, or no extractable text.
    """
    parser = _PARSERS.get(_extension(filename, content_type))
    if parser is None:
        raise ParseError(f"unsupported file type: {filename!r} ({content_type})")
    try:
        sections = [s for s in parser(data) if s.text.strip()]
    except ParseError:
        raise
    except Exception as exc:  # third-party parsers raise many unrelated types
        raise ParseError(f"could not read {filename!r}: {exc}") from exc
    if not sections:
        raise ParseError(f"no text found in {filename!r} (scanned image?)")
    return sections


def is_supported(filename: str, content_type: str) -> bool:
    """Whether `parse` has a parser for this file, judged by name or declared type."""
    return _extension(filename, content_type) in _PARSERS


def _extension(filename: str, content_type: str) -> str:
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix in _PARSERS:
        return suffix
    return _CONTENT_TYPES.get(content_type.split(";")[0].strip().lower(), suffix)


def _parse_pdf(data: bytes) -> list[Section]:
    pdf = pdfium.PdfDocument(data)
    sections = []
    try:
        for number in range(len(pdf)):
            page = pdf[number]
            textpage = page.get_textpage()
            sections.append(Section(textpage.get_text_range(), f"p. {number + 1}"))
            textpage.close()
            page.close()
    finally:
        pdf.close()
    return sections


def _heading_level(style_name: str) -> int | None:
    match = re.fullmatch(r"Heading (\d)", style_name or "")
    return int(match.group(1)) if match else None


def _parse_docx(data: bytes) -> list[Section]:
    document = DocxDocument(io.BytesIO(data))
    trail: list[str] = []
    sections: list[Section] = []
    lines: list[str] = []

    def flush() -> None:
        if lines:
            sections.append(Section("\n".join(lines), " > ".join(trail) or "Document"))
            lines.clear()

    for block in document.iter_inner_content():
        if hasattr(block, "rows"):  # a table: one line per row
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
            continue
        level = _heading_level(block.style.name if block.style else "")
        if level is not None and block.text.strip():
            flush()
            del trail[level - 1 :]
            trail.append(block.text.strip())
        elif block.text.strip():
            lines.append(block.text.strip())
    flush()
    return sections


def _parse_text(data: bytes) -> list[Section]:
    text = data.decode("utf-8", errors="replace")
    sections: list[Section] = []
    heading = "Document"
    buffer: list[str] = []
    for line in text.splitlines():
        match = re.match(r"#{1,6}\s+(.*)", line)
        if match:
            if buffer:
                sections.append(Section("\n".join(buffer), heading))
                buffer = []
            heading = match.group(1).strip() or heading
        else:
            buffer.append(line)
    if buffer:
        sections.append(Section("\n".join(buffer), heading))
    return sections


def _parse_eml(data: bytes) -> list[Section]:
    message = BytesParser(policy=policy.default).parsebytes(data)
    header = (
        f"From: {message['from']}\nTo: {message['to']}\nSubject: {message['subject']}"
    )
    body = message.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body is not None else ""
    if body is not None and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    subject = str(message["subject"] or "email")
    return [Section(f"{header}\n\n{text}", f"Email: {subject}")]


_PARSERS: dict[str, Callable[[bytes], list[Section]]] = {
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".txt": _parse_text,
    ".md": _parse_text,
    ".eml": _parse_eml,
}
_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "message/rfc822": ".eml",
}
