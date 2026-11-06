from app.core.cache import TtlLruCache
from app.llm.base import Embedder


class CachingEmbedder:
    """Remembers query embeddings so a repeated or pre-fetched question costs no call.

    Only single-text calls (questions) are cached; batches (indexing passages) go
    straight through, so the cache never fills with document text.
    """

    def __init__(
        self, inner: Embedder, maxsize: int = 1024, ttl_seconds: float = 86_400
    ) -> None:
        self._inner = inner
        self._cache: TtlLruCache[str, list[float]] = TtlLruCache(maxsize, ttl_seconds)

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        if len(texts) != 1:
            return self._inner.embed(texts)
        key = " ".join(texts[0].split()).lower()
        cached = self._cache.get(key)
        if cached is not None:
            return [cached]
        vector = self._inner.embed(texts)[0]
        self._cache.put(key, vector)
        return [vector]
