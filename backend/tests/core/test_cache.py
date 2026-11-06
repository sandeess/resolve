from app.core.cache import TtlLruCache
from app.rag.cache import normalise_question


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_least_recently_used_entry_is_evicted() -> None:
    cache: TtlLruCache[str, int] = TtlLruCache(2, 100)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # touching "a" makes "b" the oldest
    cache.put("c", 3)
    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (1, None, 3)
    assert len(cache) == 2


def test_entries_expire() -> None:
    clock = Clock()
    cache: TtlLruCache[str, int] = TtlLruCache(10, 60, clock)
    cache.put("a", 1)
    clock.now = 59
    assert cache.get("a") == 1
    clock.now = 61
    assert cache.get("a") is None
    assert len(cache) == 0


def test_zero_size_disables_caching_and_clear_empties() -> None:
    off: TtlLruCache[str, int] = TtlLruCache(0, 60)
    off.put("a", 1)
    assert off.get("a") is None
    on: TtlLruCache[str, int] = TtlLruCache(5, 60)
    on.put("a", 1)
    on.clear()
    assert on.get("a") is None


def test_question_normalisation_ignores_case_spacing_and_trailing_punctuation() -> None:
    forms = [
        "How are dates written?",
        "  how   are DATES written ",
        "how are dates written?!",
    ]
    assert len({normalise_question(q) for q in forms}) == 1
    assert normalise_question("How are dates written?") != normalise_question(
        "How are figures written?"
    )
