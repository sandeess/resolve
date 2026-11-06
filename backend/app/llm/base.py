from typing import Protocol


class Embedder(Protocol):
    """Turns text into fixed-size vectors."""

    @property
    def model_name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatModel(Protocol):
    """A single-turn chat completion."""

    def complete(self, *, system: str, user: str) -> str: ...


class LlmError(RuntimeError):
    """The model gateway failed or returned something unusable."""
