"""Clients for the LiteLLM proxy (OpenAI-compatible API).

The app never talks to a model vendor directly: model choice, fallbacks and
budgets live in the proxy config (`deploy/litellm.yaml`).
"""

from openai import OpenAI, OpenAIError

from app.llm.base import LlmError
from app.models import EMBEDDING_DIM

_EMBED_BATCH = 64
_MAX_ANSWER_TOKENS = 500  # answers are short JSON; bounds a runaway generation


class GatewayEmbedder:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            batch = texts[start : start + _EMBED_BATCH]
            try:
                response = self._client.embeddings.create(
                    model=self._model, input=batch
                )
            except OpenAIError as exc:
                raise LlmError(f"embedding request failed: {exc}") from exc
            vectors.extend(item.embedding for item in response.data)
        if any(len(v) != EMBEDDING_DIM for v in vectors):
            raise LlmError(
                f"embedding model {self._model!r} returned vectors that are not "
                f"{EMBEDDING_DIM}-dimensional"
            )
        return vectors


class GatewayChat:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, *, system: str, user: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                max_tokens=_MAX_ANSWER_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except OpenAIError as exc:
            raise LlmError(f"chat request failed: {exc}") from exc
        return response.choices[0].message.content or ""
