import io

import pytest
from docx import Document

from app.ingestion.parsers import ParseError, Section, parse


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 10 50 Td ({text}) Tj ET"
    return (
        "%PDF-1.4\n"
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 100]/Contents 4 0 R"
        "/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        f"4 0 obj<</Length {len(stream)}>>stream\n{stream}\nendstream endobj\n"
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        "trailer<</Root 1 0 R/Size 6>>\n%%EOF\n"
    ).encode()


def _docx() -> bytes:
    doc = Document()
    doc.add_heading("Style", level=1)
    doc.add_paragraph("Intro text.")
    doc.add_heading("References", level=2)
    doc.add_paragraph("Use author-date format.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Journal"
    table.rows[0].cells[1].text = "Abbrev"
    doc.add_heading("Dates", level=2)
    doc.add_paragraph("Write dates as 5 November 2026.")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_pdf_pages_become_sections() -> None:
    sections = parse(
        filename="a.pdf", content_type="application/pdf", data=_pdf("Hello references")
    )
    assert sections == [Section("Hello references", "p. 1")]


def test_docx_keeps_heading_path_and_tables() -> None:
    sections = parse(filename="s.docx", content_type="", data=_docx())
    by_locator = {s.locator: s.text for s in sections}
    assert by_locator["Style"] == "Intro text."
    assert "Use author-date format." in by_locator["Style > References"]
    assert "Journal | Abbrev" in by_locator["Style > References"]
    assert by_locator["Style > Dates"] == "Write dates as 5 November 2026."


def test_markdown_headings() -> None:
    data = b"preamble\n# Fonts\nUse Times.\n## Size\n12pt"
    sections = parse(filename="g.md", content_type="text/markdown", data=data)
    assert [(s.locator, s.text) for s in sections] == [
        ("Document", "preamble"),
        ("Fonts", "Use Times."),
        ("Size", "12pt"),
    ]


def test_eml_body_and_headers() -> None:
    raw = b"From: a@x.org\nTo: b@y.org\nSubject: Figure sizes\n\nPlease keep figures under 5 MB."
    (section,) = parse(filename="m.eml", content_type="message/rfc822", data=raw)
    assert section.locator == "Email: Figure sizes"
    assert "under 5 MB" in section.text and "From: a@x.org" in section.text


def test_type_falls_back_to_content_type() -> None:
    (section,) = parse(
        filename="upload", content_type="text/plain; charset=utf-8", data=b"hi"
    )
    assert section.text == "hi"


@pytest.mark.parametrize(
    ("filename", "data"),
    [
        ("x.exe", b"MZ"),
        ("empty.txt", b"  \n"),
        ("bad.pdf", b"not a pdf"),
        ("bad.docx", b"junk"),
    ],
)
def test_unreadable_files_raise_parse_error(filename: str, data: bytes) -> None:
    with pytest.raises(ParseError):
        parse(filename=filename, content_type="application/octet-stream", data=data)
