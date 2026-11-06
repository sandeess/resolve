# Evaluation report

Generated 2026-11-06 05:57 UTC. Synthetic corpus, seed 7, 168 golden questions. Embeddings `embed`, chat `chat-large (see deploy/litellm.yaml)`.

## Retrieval ablation

Did the passage containing the answer rank in the top k? Only answerable questions are scored. *Paraphrase* questions share no keywords with the answer sentence.

| Configuration | recall@1 | recall@3 | recall@5 | MRR | recall@5 lexical | recall@5 paraphrase |
|---|---|---|---|---|---|---|
| keyword only (full-text) | 52.2% | 61.6% | 65.2% | 0.583 | 97.3% | 27.0% |
| vector only, raw passages | 84.8% | 97.8% | 97.8% | 0.909 | 100.0% | 95.2% |
| vector only, with context prefix | 82.6% | 97.8% | 97.8% | 0.896 | 100.0% | 95.2% |
| hybrid, raw passages, keyword weight 0.04 | 77.5% | 97.1% | 97.8% | 0.866 | 100.0% | 95.2% |
| hybrid, with context prefix, keyword weight 1 | 69.6% | 87.0% | 89.9% | 0.790 | 100.0% | 77.8% |
| hybrid, with context prefix, keyword weight 0.5 | 71.0% | 87.0% | 89.9% | 0.797 | 100.0% | 77.8% |
| hybrid, with context prefix, keyword weight 0.3 | 71.7% | 87.0% | 89.9% | 0.805 | 100.0% | 77.8% |
| hybrid, with context prefix, keyword weight 0.15 | 73.2% | 89.1% | 95.7% | 0.824 | 100.0% | 90.5% |
| hybrid, with context prefix, keyword weight 0.08 | 73.2% | 92.0% | 97.8% | 0.831 | 100.0% | 95.2% |
| hybrid, with context prefix, keyword weight 0.04 (default) | 76.1% | 96.4% | 97.8% | 0.856 | 100.0% | 95.2% |

## End to end (the real Ask flow)

A question passes when the answer states the expected value, cites a passage that contains the evidence, and mentions no forbidden value (stale or another journal's). Questions that must be refused pass only if Ask abstains.

- Overall pass rate: **94.6%** (168 questions, 0 errors)
- Answerable questions passed: 93.5%; falsely abstained: 5.8%
- Unanswerable / unapproved questions correctly refused: 100.0%
- Answers citing the evidence passage: 100.0%
- Answers mentioning a forbidden value (stale / leaked): 0.0%
- Latency p50 / p95: 1.0s / 2.0s

| Question type | n | pass rate |
|---|---|---|
| article | 6 | 100.0% |
| article_isolation | 6 | 100.0% |
| fact | 72 | 88.9% |
| stale | 36 | 97.2% |
| ticket | 18 | 100.0% |
| unanswerable | 24 | 100.0% |
| unapproved_trap | 6 | 100.0% |

## Failures

- `JA-contributions-par` (fact, paraphrase): Who did what: how do we state each person's role? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-spelling-par` (fact, paraphrase): Should colour be spelled with a u? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-units-par` (stale, paraphrase): Do we report distances in metres or miles? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-data_statement-lex` (fact, lexical): Is a data availability statement required? -> missing value; cited ['Author guidelines.md v2']; answer: 'A data availability statement is not required [1].'
- `JB-contributions-par` (fact, paraphrase): Who did what: how do we state each person's role? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-spelling-par` (fact, paraphrase): Should colour be spelled with a u? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-tables-par` (fact, paraphrase): In what form do you want the data grids? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-ethics-par` (fact, paraphrase): Do I need to mention committee clearance for my study? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-contributions-par` (fact, paraphrase): Who did what: how do we state each person's role? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
