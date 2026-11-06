import math

import pytest
from metrics import (
    contains,
    first_relevant_rank,
    mean_reciprocal_rank,
    percentile,
    rate,
    recall_at_k,
)


def test_rank_is_one_based_and_ignores_whitespace_and_case() -> None:
    passages = ["nothing here", "Figures   must be\nsupplied as TIFF files.", "later"]
    assert first_relevant_rank(passages, "figures must be supplied as tiff files.") == 2
    assert first_relevant_rank(passages, "PNG") is None


def test_stale_value_is_not_a_hit() -> None:
    assert (
        first_relevant_rank(
            ["Figures must be supplied as TIFF files."],
            "Figures must be supplied as PNG files.",
        )
        is None
    )


def test_recall_and_mrr() -> None:
    ranks = [1, 3, None, 6]
    assert recall_at_k(ranks, 1) == 0.25
    assert recall_at_k(ranks, 5) == 0.5
    assert mean_reciprocal_rank(ranks) == pytest.approx((1 + 1 / 3 + 0 + 1 / 6) / 4)


def test_empty_inputs_are_nan_not_zero() -> None:
    assert math.isnan(recall_at_k([], 5))
    assert math.isnan(mean_reciprocal_rank([]))
    assert math.isnan(percentile([], 50))
    assert math.isnan(rate([]))


@pytest.mark.parametrize(
    ("q", "expected"), [(0, 1.0), (50, 2.5), (100, 4.0), (95, 3.85)]
)
def test_percentile_interpolates(q: float, expected: float) -> None:
    assert percentile([4, 1, 3, 2], q) == pytest.approx(expected)


def test_contains_normalises() -> None:
    assert contains("Use  SI\nunits", "si units")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("after the 12-month embargo", "12 months"),
        ("limited to five keywords", "5 keywords"),
        ("Dates use YYYY-MM-DD.", "yyyy mm dd"),
        ("Tables as Excel files", "Excel file"),
    ],
)
def test_phrasing_variants_match(answer: str, expected: str) -> None:
    assert contains(answer, expected)


@pytest.mark.parametrize(
    ("answer", "other"),
    [
        ("embargo of 12 months", "18 months"),
        ("Month DD, YYYY", "DD Month YYYY"),
        ("SI units", "US customary units"),
        ("300 dpi", "600 dpi"),
    ],
)
def test_different_values_stay_different(answer: str, other: str) -> None:
    assert not contains(answer, other)


@pytest.mark.parametrize(
    ("answer", "needle", "expected"),
    [
        (
            "A statement is only required for empirical studies.",
            "only for empirical studies",
            True,
        ),
        (
            "Markdown file",
            "a Markdown file",
            True,
        ),  # a leading article is ignored
        ("Use SI units throughout", "SI units", True),
        ("Not SI, use US customary units", "SI units", False),
        ("Dates as Month DD, YYYY", "DD Month YYYY", False),
        ("300 dpi minimum", "600 dpi", False),
    ],
)
def test_in_order_matching_for_answers(
    answer: str, needle: str, expected: bool
) -> None:
    from metrics import contains_in_order

    assert contains_in_order(answer, needle) is expected
