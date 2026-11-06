# Evaluation

Measures the product through its real services (upload, ingestion, tickets, retrieval, Ask), on a synthetic corpus that is generated from a seed. No real data is involved.

```bash
cd backend
uv run python ../eval/run_eval.py                # full run: ablation + end to end (needs LiteLLM up)
uv run python ../eval/run_eval.py --skip-e2e     # retrieval ablation only, no chat calls
uv run python ../eval/run_eval.py --limit 30     # first 30 questions end to end
uv run python ../eval/run_eval.py --check        # exit 1 if below eval/thresholds.json
```

Each run starts a throwaway pgvector container, writes `reports/latest.md` (the table that goes in the README) and a timestamped JSON with every per-question outcome. Embeddings are cached in `.cache/` (git-ignored) so reruns are free and exact.

## What is measured

**Retrieval ablation.** Did the passage that contains the answer rank in the top *k*? A passage counts only if it contains the exact evidence sentence, which includes the value, so a stale revision of the same rule is a miss. Configurations: full-text only, vector only, hybrid, each with and without the context prefix (document name and section prepended before embedding).

**End to end.** The real Ask flow. A question passes when the answer states the expected value, cites a passage containing the evidence, and mentions no forbidden value. Questions that must be refused pass only if Ask abstains.

## Question types (the traps)

| Type | What it guards against |
|---|---|
| `fact` | Another journal's value leaking into the answer |
| `stale` | The previous revision of a rule being served |
| `article` / `article_isolation` | An article-level exception missing, or leaking into journal-wide answers |
| `ticket` | Approved ticket answers not being found |
| `unapproved_trap` | A resolved-but-unapproved ticket being used as knowledge |
| `unanswerable` | Guessing instead of abstaining |

*Lexical* questions share keywords with the answer sentence; *paraphrase* questions deliberately do not (a unit test enforces this), which is where vector search should earn its keep.

## Findings so far

Baseline (`reports/baseline-2026-11-05.md`) to current (`reports/latest.md`), same seed. The corpus got harder in between (12 distractor notes per journal), so absolute numbers are not comparable; the *causes* are the point.

1. **Full-text matching was crippled by `plainto_tsquery`**, which requires every question word to appear. Switching to "any word" lifted keyword-only recall@5 from 25% to 65% (97% on lexical questions).
2. **Equal-weight hybrid was worse than vector alone** once distractors existed: recall@5 89.9% vs 97.8%, MRR 0.79 vs 0.90. The keyword ranker pushed correct passages down on paraphrased questions. Lowering the keyword weight in the fusion converged on vector-only quality; 0.04 (now the default `KEYWORD_WEIGHT`) matched it on two seeded corpora. **No weight beat vector-only here**, so hybrid is kept only as a tie-breaker for exact terms (identifiers, codes), which this corpus does not exercise. Re-test on real documents before relying on that.
3. **The context prefix did not help** (recall@1 82.6% with it vs 84.8% without). It stays for now because the difference is within noise at this size, but there is no evidence it earns its cost.
4. **Article exceptions needed an explicit precedence rule** in the prompt (article-scope sources override journal-scope ones); the answers were already stating the exception, but the grader and the prompt now both reflect the intended behaviour.
5. **Most baseline "failures" were the grader**, not the system (hyphens, plurals, wording). The grader now ignores those, and a unit test pins that distinct values stay distinct.

Remaining failures are mostly paraphrases the model refuses ("a note to the editor" for *cover letter*, "who did what" for *contributions*), plus a terse "miles" answer for a units rule.

The weight was tuned on seed 7 and confirmed on seed 11. Both use the same question templates, so this checks value and distractor variation, not wording generalisation.

## Model provider and speed

The project uses **DeepInfra** (one key for embeddings and chat, through LiteLLM; see `deploy/litellm.yaml`). The embedding model is `BAAI/bge-m3`, so retrieval numbers do not depend on the chat model.

Chat models compared on the same 168 questions (each in `reports/`):

| Alias / model | Pass rate | Falsely refused | Latency p50 / p95 |
|---|---|---|---|
| `chat-large` Llama-3.3-70B-Instruct-Turbo | 97.0% | 2.9% | 1.6s / 3.3s |
| **`chat-fast` Llama-4-Maverick-17B** (default) | 95.8% | 2.2% | 1.1s / 2.0s |
| Mistral-Small-3.2-24B | 94.6% | 5.8% | 1.0s / 2.0s |
| `chat-small` Llama-3.1-8B-Instruct | 79.8% | 15.2% | 1.6s / 2.3s |

All four refused every unanswerable question and none leaked a stale or other-journal value (the 8B refused 96.7%). Maverick gives up about one point (two questions, within run-to-run noise) for roughly a third off the median and 40% off the tail; a separate 35-call timing showed the 70B's latency to be erratic (median 3.1s, one call at 19s) while Maverick stayed between 0.8s and 1.2s. `chat-large` stays as the quality option and as the automatic fallback if `chat-fast` errors (configured in LiteLLM, not exercised: the proxy refuses to simulate failures by default).

Where the time goes in one Ask (healthy network): embedding the question about 0.4s, the database search under 0.05s, the model about 0.6-1.5s. The proxy hop costs about 0.2s. The network matters more than anything in our code: during one session the round trip to DeepInfra swung from 260ms to 1.5s, which doubled every figure. That is why the biggest wins are fewer round trips, not faster code:

- **Prefetch**: the UI embeds the question about 0.6s after typing pauses, so pressing Enter leaves only the model call (cold Ask 2.1s median, after prefetch 1.7s in one run).
- **Answer cache**: an identical question (any case, spacing or trailing punctuation) is answered in milliseconds while the journal's knowledge is unchanged. Keys include journal, article and a fingerprint that moves when a document is uploaded or indexed or a ticket answer is approved, reopened or changed; permission is checked before the cache is read. Evaluations bypass it (`use_cache=False`).
- **Bounded failure**: 30s timeout and one retry instead of the SDK's 10-minute default.

Streaming was considered and skipped: answers are about 30 tokens, so the model streams for well under a second and the wait is the round trip to first token, which streaming does not shorten.

## Limits to keep in mind

- The corpus is synthetic and templated, so absolute numbers are friendlier than real documents will give. The *differences* between configurations and the trap results are the useful part; re-run on real documents before trusting any absolute figure.
- Answer checks are string-based (expected value present, forbidden value absent), not an LLM judge. They can fail a correct answer that is phrased differently and cannot detect a subtly wrong explanation.
- There is no reranker in the ablation yet.
- The chat model is not pinned beyond the LiteLLM alias, so end-to-end numbers move when the model behind it changes.
