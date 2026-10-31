# Retrieval evaluation — 31 October 2026

This is a small engineering check with live Supabase/Gemini retrieval and source
inspection by the coding assistant. It is **not an independent human assessment** or
a representative accuracy benchmark. Reviewable questions, source-page links, ratings
and measurements are in [cases](../evals/retrieval_cases.json),
[review notes](../evals/retrieval_review.json) and [results](../evals/retrieval_results.json).

## What actually ran

CCL's complete active corpus: one annual report and two transcripts, 694 chunks.
Four answerable questions cover private-label manufacturing, cost-plus economics,
the undecided expansion location and coffee consumption/product mix. Two questions
select settings; two are a fixed parameter hold-out. One additional question asks
for unavailable FY2030 audited revenue and should produce no claims.

The wider labelled set contains ten positives across CCL, INFY and POLYCAB plus two
negatives. **Seven cases have not run.** Live Gemini returned a daily quota violation
at the 1,000-text free-tier limit: batched texts each consume an input request. CCL is
694/694 indexed, INFY 264/1,125, POLYCAB 0/1,378. Other active company corpora remain
keyword-only. No partial index or different company was substituted in this evaluation.
The backfill is checkpointed and can resume after allowance resets.

## A baseline defect found before comparing AI

The original selector allowed only four passages per document. Every evaluated query
selects one annual report or one transcript, so useful keyword passages at ranks 5–8
were discarded. Original keyword reference-page Recall@5 and @10 were both 0.25.

The selector now adapts the document cap to the number of documents represented in
the candidates: one document can fill the ten-passage budget; three documents retain
the original four-per-document cap. Two passages per page remains the limit. Both
keyword and hybrid use this correction. Its gain must not be attributed to embeddings.

## Results with the corrected, matched keyword baseline

Recall measures curated **reference PDF pages**, not every potentially relevant page.
Ranking slots are chunks and reference pages are deduplicated. For example, keyword
answers correctly cite annual-report page 60 although the private-label case's reference
pages are 4 and 11. A reference-page miss does not establish a bad answer.

| Measure | Keyword | Hybrid |
| --- | ---: | ---: |
| Macro reference-page Recall@5, four positives | 0.500 | 1.000 |
| Macro reference-page Recall@10, four positives | 0.875 | 1.000 |
| Development Recall@5 / @10, two queries | 0.500 / 0.750 | 1.000 / 1.000 |
| Hold-out Recall@5 / @10, two queries | 0.500 / 1.000 | 1.000 / 1.000 |
| Reviewed validated-answer quality, mean out of 2 | 1.75 | 1.75 |
| Unsupported-question abstention | 1/1 | 1/1 |
| Median warmed retrieval, 15 measurements per method | 461 ms | 1,403 ms |

The warmed timing uses the selected 30-candidate settings, three interleaved repetitions
over five cases, actual database calls, and cached question embeddings with **zero
embedding-provider calls**. It excludes document ingestion and answer generation.
It measures operator-to-service round trips, not Render end-to-end response time.
The first 60-candidate collection pass had a 3,752 ms hybrid median, including a mix
of cached and uncached question embeddings; it is not a pure cold-cache estimate.

## Settings and interpretation

Twelve development-only combinations varied candidate counts (30/60), RRF constant
(10/60), and semantic weight (0.5/1/2). The selected settings are **30 candidates per
branch, k=10, semantic weight=2**, at most ten evidence passages and two per page,
with the adaptive document cap. Sixty candidates supplied no additional reference-page
gain. Larger budgets were therefore unnecessary. The original keyword baseline is
explicitly frozen in the script; a matched keyword arm controls for the cap correction.

These weights are provisional: two development questions are insufficient to establish
general settings for Indian equities. Re-evaluate the remaining labelled companies as
their complete indexes become available. Hold-out questions did not select parameters;
this was not a blinded or independently adjudicated study.

Semantic search improves how early the known supporting pages appear here. It did
**not improve reviewed final-answer quality** over corrected keyword retrieval, and
adds about 0.94 seconds to warmed retrieval. Broader evidence is needed before claiming
an answer-quality advantage. The default rollout flag remains off; the implementation
supports a controlled trial on fully indexed companies and immediate keyword rollback.

## Source review and remaining issues

Both methods answer the location question after the cap correction. Both correctly
abstain on future audited revenue. A hybrid draft added unchanged **EBITDA** to a quote
about **margin**. A new conservative metric-name check withholds that entire claim and
also prevents reuse of a cached answer with the same mismatch. The existing annual-table
number guard separately withheld one keyword draft claim. Final answers were rated
after these checks; generation used the same unchanged model/prompt for both methods.

Both demand answers still need clearer attribution of management observations. Exact
quotes and named-metric matching do not prove every paraphrase, causal statement or
unit/period relationship. Financial table comparisons remain disabled. The review
records this limitation rather than treating a valid quotation as complete entailment.

## Repeat the work

```powershell
.venv\Scripts\python scripts/evaluate_retrieval.py collect --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py tune --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py answers --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py latency --symbols CCL
```

Without `--symbols CCL`, collection attempts the wider set and skips incomplete indexes;
tuning refuses a missing positive case. This avoids publishing a partial run as a full
cross-company benchmark. Answer replay reuses a draft only with the same evidence IDs
and model and reruns validation. Raw passages, drafts, timings and API job results stay
in ignored local `artifacts/`; committed results contain source links, metrics and notes.
