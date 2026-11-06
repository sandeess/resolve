"""A cheap fingerprint of what a journal currently "knows".

Used to invalidate cached answers. It changes when:

* a document version is uploaded (the newest version's timestamp moves, which also
  flips which version is current, even before the new one is indexed),
* indexing finishes or a ticket answer is approved or withdrawn (chunk count),
* a ticket changes (its `updated_at`).
"""

import uuid

from sqlalchemy import text
from sqlmodel import Session


def knowledge_fingerprint(session: Session, journal_id: uuid.UUID) -> str:
    row = session.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM chunk WHERE journal_id = :j),
              (SELECT max(v.created_at) FROM documentversion v
                 JOIN document d ON d.id = v.document_id WHERE d.journal_id = :j),
              (SELECT max(updated_at) FROM ticket WHERE journal_id = :j)
            """
        ),
        {"j": journal_id},
    ).one()
    return "|".join(str(part) for part in row)
