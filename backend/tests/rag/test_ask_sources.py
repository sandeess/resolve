import uuid

from app.rag.ask import SYSTEM_PROMPT, _render_source
from app.rag.retrieval import Hit


def _ticket_hit(number: int, dated: str) -> Hit:
    return Hit(
        chunk_id=uuid.uuid4(),
        source_type="ticket",
        source_name=f"T-{number}",
        locator="q",
        content="Answer: 150 words",
        score=1.0,
        ticket_number=number,
        dated=dated,
    )


def test_sources_carry_their_date_so_conflicts_can_be_resolved_by_recency() -> None:
    rendered = _render_source(1, _ticket_hit(4, "2026-11-06T09:33"))
    assert 'date="2026-11-06T09:33"' in rendered


def test_prompt_forbids_blending_conflicting_sources() -> None:
    assert "Never blend conflicting values" in SYSTEM_PROMPT
    assert "most recent date" in SYSTEM_PROMPT
