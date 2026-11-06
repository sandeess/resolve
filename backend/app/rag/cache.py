"""Ask-answer caching helpers.

Answers are cached per process, keyed by journal, article, the normalised
question and a *knowledge fingerprint* (see `knowledge.py`). The fingerprint
changes whenever a document is revised or indexed or a ticket answer is approved
or withdrawn, so a cached answer can never outlive the knowledge it was built from.
"""

import re
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerKey:
    journal_id: uuid.UUID
    article_id: uuid.UUID | None
    question: str
    fingerprint: str


def normalise_question(question: str) -> str:
    """Case, spacing and trailing punctuation do not change what is being asked."""
    return re.sub(r"\s+", " ", question).strip().rstrip("?!. ").lower()
