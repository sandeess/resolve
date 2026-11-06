"""Evaluation CLI: retrieval ablation + end-to-end Ask quality.

Run from the backend directory (settings and the venv live there):

    cd backend
    uv run python ../eval/run_eval.py                 # full run
    uv run python ../eval/run_eval.py --skip-e2e      # retrieval ablation only
    uv run python ../eval/run_eval.py --check         # fail below eval/thresholds.json
"""

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))

from corpus import build_corpus  # noqa: E402
from harness import (  # noqa: E402
    CachedEmbedder,
    E2ESummary,
    ItemOutcome,
    RetrievalRow,
    end_to_end,
    eval_database,
    retrieval_ablation,
    summarise,
)

from app.core.providers import get_chat_model, get_embedder  # noqa: E402

DEFAULT_THRESHOLDS = EVAL_DIR / "thresholds.json"


def pct(value: float) -> str:
    return "n/a" if value != value else f"{value * 100:.1f}%"


def render_markdown(
    seed: int,
    n_items: int,
    rows: list[RetrievalRow],
    summary: E2ESummary | None,
    failures: list[ItemOutcome],
    models: dict[str, str],
) -> str:
    out = [
        "# Evaluation report",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Synthetic corpus, seed {seed}, "
        f"{n_items} golden questions. Embeddings `{models['embed']}`, chat `{models['chat']}`.",
        "",
        "## Retrieval ablation",
        "",
        "Did the passage containing the answer rank in the top k? Only answerable questions "
        "are scored. *Paraphrase* questions share no keywords with the answer sentence.",
        "",
        "| Configuration | recall@1 | recall@3 | recall@5 | MRR | recall@5 lexical | recall@5 paraphrase |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r.config} | {pct(r.recall_1)} | {pct(r.recall_3)} | {pct(r.recall_5)} | "
            f"{r.mrr:.3f} | {pct(r.lexical_recall_5)} | {pct(r.paraphrase_recall_5)} |"
        )
    if summary:
        out += [
            "",
            "## End to end (the real Ask flow)",
            "",
            "A question passes when the answer states the expected value, cites a passage that "
            "contains the evidence, and mentions no forbidden value (stale or another journal's). "
            "Questions that must be refused pass only if Ask abstains.",
            "",
            f"- Overall pass rate: **{pct(summary.pass_rate)}** ({summary.n} questions, {summary.error_count} errors)",
            f"- Answerable questions passed: {pct(summary.answerable_pass_rate)}; falsely abstained: {pct(summary.false_abstention_rate)}",
            f"- Unanswerable / unapproved questions correctly refused: {pct(summary.abstention_recall)}",
            f"- Answers citing the evidence passage: {pct(summary.citation_rate)}",
            f"- Answers mentioning a forbidden value (stale / leaked): {pct(summary.forbidden_leak_rate)}",
            f"- Latency p50 / p95: {summary.p50_seconds:.1f}s / {summary.p95_seconds:.1f}s",
            "",
            "| Question type | n | pass rate |",
            "|---|---|---|",
            *[f"| {t} | {n} | {pct(p)} |" for t, (n, p) in summary.by_type.items()],
        ]
        if failures:
            out += ["", "## Failures", ""]
            for f in failures[:25]:
                why = f.error or (
                    f"forbidden {f.forbidden_hit}"
                    if f.forbidden_hit
                    else "wrong abstention"
                    if f.abstained != f.expect_abstain
                    else "missing value"
                    if not f.answer_ok
                    else "evidence not cited"
                )
                out.append(
                    f"- `{f.id}` ({f.type}, {f.style}): {f.question} -> {why}; cited {f.cited}; answer: {f.answer[:140]!r}"
                )
    return "\n".join(out) + "\n"


def check(
    thresholds_path: Path, rows: list[RetrievalRow], summary: E2ESummary | None
) -> list[str]:
    limits = json.loads(thresholds_path.read_text())
    default = next(r for r in rows if "(default)" in r.config)
    measured = {
        "default_recall_5_min": default.recall_5,
        "default_mrr_min": default.mrr,
    }
    if summary:
        measured |= {
            "pass_rate_min": summary.pass_rate,
            "abstention_recall_min": summary.abstention_recall,
            "forbidden_leak_rate_max": summary.forbidden_leak_rate,
        }
    problems = []
    for key, limit in limits.items():
        if key not in measured:
            continue
        value = measured[key]
        bad = value > limit if key.endswith("_max") else value < limit
        if bad:
            problems.append(f"{key}: measured {value:.3f}, limit {limit}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--journals", type=int, default=3)
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="retrieval ablation only (no chat calls)",
    )
    parser.add_argument(
        "--limit", type=int, help="only the first N golden questions end to end"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--dsn", help="use this Postgres instead of a throwaway container"
    )
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if below the thresholds file"
    )
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "reports")
    args = parser.parse_args()

    corpus = build_corpus(args.seed, args.journals)
    (EVAL_DIR / "golden_qa.jsonl").write_text(corpus.golden_jsonl(), encoding="utf-8")
    print(
        f"corpus: {len(corpus.docs)} documents, {len(corpus.tickets)} tickets, {len(corpus.golden)} questions"
    )

    embedder = CachedEmbedder(get_embedder(), EVAL_DIR / ".cache" / "embeddings.json")
    chat = get_chat_model()
    with eval_database(args.dsn) as engine, tempfile.TemporaryDirectory() as tmp:
        print("retrieval ablation")
        rows, seeded = retrieval_ablation(engine, corpus, embedder, Path(tmp))
        embedder.save()
        print(f"  embeddings: {embedder.misses} computed, {embedder.hits} from cache")
        summary: E2ESummary | None = None
        outcomes: list[ItemOutcome] = []
        if not args.skip_e2e:
            print("end to end")
            outcomes = end_to_end(
                engine,
                corpus,
                seeded,
                embedder,
                chat,
                limit=args.limit,
                workers=args.workers,
            )
            embedder.save()
            summary = summarise(outcomes)

    failures = [o for o in outcomes if not o.passed]
    models = {
        "embed": embedder.model_name,
        "chat": "chat-large (see deploy/litellm.yaml)",
    }
    report = render_markdown(
        args.seed, len(corpus.golden), rows, summary, failures, models
    )
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (args.out / "latest.md").write_text(report, encoding="utf-8")
    (args.out / f"{stamp}.json").write_text(
        json.dumps(
            {
                "seed": args.seed,
                "retrieval": [asdict(r) for r in rows],
                "e2e": asdict(summary) if summary else None,
                "outcomes": [asdict(o) for o in outcomes],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)

    if args.check:
        problems = check(args.thresholds, rows, summary)
        for p in problems:
            print(f"THRESHOLD FAILED: {p}", file=sys.stderr)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
