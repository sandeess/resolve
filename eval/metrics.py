"""Pure metric helpers; no I/O, so they are unit-tested exhaustively."""

import math
import re
from collections.abc import Iterable, Sequence

_TOKEN = re.compile(r"\w+(?:[,.']\w+)*")
_NUMBER_WORDS = {
    word: str(n)
    for n, word in enumerate(
        (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
        )
    )
}


def _stem(token: str) -> str:
    token = _NUMBER_WORDS.get(token, token)
    return (
        token[:-1]
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss")
        else token
    )


def normalise(text: str) -> str:
    """Case, spacing, hyphens, simple plurals and number words ("five" == "5") are
    ignored, so "12-month embargo" matches "12 months" without weakening the check
    (distinct values stay distinct)."""
    return " ".join(
        _stem(t)
        for t in _TOKEN.findall(text.lower().replace("-", " ").replace("_", " "))
    )


def contains(text: str, needle: str) -> bool:
    return normalise(needle) in normalise(text)


_ARTICLES = {"a", "an", "the"}


def contains_in_order(text: str, needle: str, max_gap: int = 1) -> bool:
    """True if the needle's words appear in order with at most `max_gap` words
    between neighbours. A leading article ("a Markdown file") is ignored.

    Used for *answers*: "only required for empirical studies" states the value
    "only for empirical studies". The gap limit keeps "Not SI, use US customary
    units" from satisfying "SI units". Evidence matching stays strict (`contains`).
    """
    wanted = normalise(needle).split()
    while wanted and wanted[0] in _ARTICLES:
        wanted.pop(0)
    haystack = normalise(text).split()
    if not wanted:
        return True
    for start, word in enumerate(haystack):
        if word != wanted[0]:
            continue
        position, ok = start, True
        for target in wanted[1:]:
            window = haystack[position + 1 : position + 2 + max_gap]
            if target not in window:
                ok = False
                break
            position += 1 + window.index(target)
        if ok:
            return True
    return False


def first_relevant_rank(passages: Sequence[str], evidence: str) -> int | None:
    """1-based rank of the first passage containing `evidence`, else None."""
    for rank, passage in enumerate(passages, start=1):
        if contains(passage, evidence):
            return rank
    return None


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    """Share of queries whose first relevant passage ranks within the top `k`."""
    if not ranks:
        return math.nan
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    if not ranks:
        return math.nan
    return sum(1 / r for r in ranks if r is not None) / len(ranks)


def percentile(values: Iterable[float], q: float) -> float:
    """Linear-interpolated percentile, `q` in [0, 100]."""
    data = sorted(values)
    if not data:
        return math.nan
    position = (len(data) - 1) * q / 100
    low, high = math.floor(position), math.ceil(position)
    return data[low] + (data[high] - data[low]) * (position - low)


def rate(flags: Sequence[bool]) -> float:
    return sum(flags) / len(flags) if flags else math.nan
