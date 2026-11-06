import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ChatModelDep, EmbedderDep, ScopeDep, SessionDep
from app.domain.policy import Action
from app.llm.base import LlmError
from app.models import AskRequest
from app.rag.ask import AskResult, ask
from app.services.access import require

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ask"])


@router.post("/journals/{journal_id}/ask", response_model=AskResult)
def ask_journal(
    session: SessionDep,
    scope: ScopeDep,
    embedder: EmbedderDep,
    chat: ChatModelDep,
    journal_id: uuid.UUID,
    body: AskRequest,
) -> AskResult:
    """Answers a question from the journal's current documents, with citations.

    Pass `article_id` to include that article's documents alongside the
    journal-level ones. If the documents do not answer it, `abstained` is true.
    """
    try:
        return ask(
            session=session,
            scope=scope,
            embedder=embedder,
            chat=chat,
            journal_id=journal_id,
            question=body.question,
            article_id=body.article_id,
        )
    except LlmError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.post(
    "/journals/{journal_id}/ask/prefetch", status_code=status.HTTP_204_NO_CONTENT
)
def prefetch_question(
    scope: ScopeDep,
    embedder: EmbedderDep,
    journal_id: uuid.UUID,
    body: AskRequest,
) -> None:
    """Embeds a question ahead of time so the real Ask skips that network call.

    The UI calls this shortly after the user stops typing. It is best effort: it
    returns 204 even if the model gateway is down, because the real Ask will
    simply do the work itself. Needs the same permission as asking.
    """
    require(scope, journal_id, Action.ASK)
    try:
        embedder.embed([body.question])
    except LlmError as exc:
        logger.info("prefetch skipped: %s", exc)
