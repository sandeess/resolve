# Evaluation report

Generated 2026-11-05 18:00 UTC. Synthetic corpus, seed 7, 168 golden questions. Embeddings `embed`, chat `chat-large (see deploy/litellm.yaml)`.

## Retrieval ablation

Did the passage containing the answer rank in the top k? Only answerable questions are scored. *Paraphrase* questions share no keywords with the answer sentence.

| Configuration | recall@1 | recall@3 | recall@5 | MRR | recall@5 lexical | recall@5 paraphrase |
|---|---|---|---|---|---|---|
| keyword only (full-text) | 55.8% | 60.9% | 65.2% | 0.602 | 97.3% | 27.0% |
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

- Overall pass rate: **79.8%** (168 questions, 0 errors)
- Answerable questions passed: 76.1%; falsely abstained: 15.2%
- Unanswerable / unapproved questions correctly refused: 96.7%
- Answers citing the evidence passage: 97.4%
- Answers mentioning a forbidden value (stale / leaked): 0.0%
- Latency p50 / p95: 1.6s / 2.3s

| Question type | n | pass rate |
|---|---|---|
| article | 6 | 100.0% |
| article_isolation | 6 | 100.0% |
| fact | 72 | 75.0% |
| stale | 36 | 75.0% |
| ticket | 18 | 66.7% |
| unanswerable | 24 | 95.8% |
| unapproved_trap | 6 | 100.0% |

## Failures

- `JA-figure_format-par` (stale, paraphrase): Which picture type do you want for the artwork? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-spelling-par` (fact, paraphrase): Should colour be spelled with a u? -> missing value; cited ['House style.md v2']; answer: 'No'
- `JA-units-par` (fact, paraphrase): Do we report distances in metres or miles? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-headings-par` (stale, paraphrase): How deeply can I nest subsections? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-keywords-par` (stale, paraphrase): How many index terms do I list under the summary? -> missing value; cited ['Author guidelines.md v2']; answer: '8'
- `JA-manuscript_format-par` (fact, paraphrase): Which kind of file do I upload for the paper itself? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-cover_letter-lex` (fact, lexical): Is a cover letter needed? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-cover_letter-par` (fact, paraphrase): Do I have to write a note to the editor when sending my paper? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-ethics-par` (fact, paraphrase): Do I need to mention committee clearance for my study? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JA-contributions-par` (fact, paraphrase): Who did what: how do we state each person's role? -> missing value; cited ['Production note 6.md v1', 'Production note 8.md v1']; answer: "The editorial office replied to a reader's question, and the production team reviewed how certain topics are handled in recent issues."
- `JA-tkt1-par` (ticket, paraphrase): How long before we nudge a referee who has not replied? -> missing value; cited ['T-14']; answer: '21 days'
- `JA-tkt2-lex` (ticket, lexical): Can authors post preprints? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-figure_format-par` (fact, paraphrase): Which picture type do you want for the artwork? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-units-par` (stale, paraphrase): Do we report distances in metres or miles? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-keywords-par` (stale, paraphrase): How many index terms do I list under the summary? -> missing value; cited ['Author guidelines.md v2']; answer: '5'
- `JB-cover_letter-par` (stale, paraphrase): Do I have to write a note to the editor when sending my paper? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-data_statement-lex` (fact, lexical): Is a data availability statement required? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-data_statement-par` (fact, paraphrase): Must I say where my datasets can be found? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-ethics-par` (fact, paraphrase): Do I need to mention committee clearance for my study? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-contributions-par` (fact, paraphrase): Who did what: how do we state each person's role? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JB-tkt1-par` (ticket, paraphrase): How long before we nudge a referee who has not replied? -> missing value; cited ['T-18']; answer: '14 days'
- `JC-figure_format-par` (stale, paraphrase): Which picture type do you want for the artwork? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-units-par` (fact, paraphrase): Do we report distances in metres or miles? -> wrong abstention; cited []; answer: "I could not find an answer in this journal's current documents."
- `JC-abstract-par` (stale, paraphrase): How long may the summary at the top be? -> missing value; cited ['Author guidelines.md v2']; answer: '150 characters'
- `JC-keywords-lex` (fact, lexical): How many keywords should be provided? -> missing value; cited ['Author guidelines.md v2']; answer: '8'
