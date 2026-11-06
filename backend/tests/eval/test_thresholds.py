import json
from pathlib import Path

from harness import E2ESummary, RetrievalRow
from run_eval import check


def _rows(recall_5: float = 0.97, mrr: float = 0.85) -> list[RetrievalRow]:
    return [RetrievalRow("hybrid (default)", 10, 0.7, 0.9, recall_5, mrr, 0.9, 1.0)]


def _summary(
    pass_rate: float = 0.95, abstain: float = 1.0, leak: float = 0.0
) -> E2ESummary:
    return E2ESummary(10, pass_rate, 0.9, 0.0, abstain, leak, 1.0, 0, 1.0, 2.0, {})


def _limits(tmp_path: Path) -> Path:
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            {
                "default_recall_5_min": 0.95,
                "default_mrr_min": 0.8,
                "pass_rate_min": 0.9,
                "forbidden_leak_rate_max": 0.0,
            }
        )
    )
    return path


def test_passes_when_every_limit_is_met(tmp_path: Path) -> None:
    assert check(_limits(tmp_path), _rows(), _summary()) == []


def test_each_violated_limit_is_reported(tmp_path: Path) -> None:
    problems = check(
        _limits(tmp_path),
        _rows(recall_5=0.9, mrr=0.5),
        _summary(pass_rate=0.5, leak=0.02),
    )
    assert len(problems) == 4
    assert any("forbidden_leak_rate_max" in p for p in problems)


def test_end_to_end_limits_are_skipped_without_an_e2e_run(tmp_path: Path) -> None:
    assert check(_limits(tmp_path), _rows(), None) == []
