from app.llm.cache import CachingEmbedder


class Counting:
    model_name = "count"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t))] for t in texts]


def test_a_repeated_question_costs_one_call_whatever_its_spacing_or_case() -> None:
    inner = Counting()
    embedder = CachingEmbedder(inner)
    first = embedder.embed(["How are dates written?"])
    again = embedder.embed(["  how are   DATES written? "])
    assert first == again and len(inner.calls) == 1


def test_batches_are_never_cached_so_indexing_does_not_fill_the_cache() -> None:
    inner = Counting()
    embedder = CachingEmbedder(inner, maxsize=2)
    embedder.embed(["a passage", "another passage"])
    embedder.embed(["a passage", "another passage"])
    assert len(inner.calls) == 2


def test_it_reports_the_wrapped_model_name() -> None:
    assert CachingEmbedder(Counting()).model_name == "count"
