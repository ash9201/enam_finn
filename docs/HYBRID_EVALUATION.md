# Retrieval evaluation — 31 October 2026

This report preserves the evaluation snapshots and decisions at their original stages.
The subsequent [production rollout](HYBRID_ROLLOUT.md) is now enabled for complete
company indexes, with keyword fallback otherwise. Its settings and these scores were
not retuned or rewritten for rollout.

This is a small engineering check with live Supabase/Gemini retrieval and source
inspection by the coding assistant. It is **not an independent human assessment** or
a representative accuracy benchmark. Reviewable questions, source-page links, ratings
and measurements are in [cases](../evals/retrieval_cases.json),
[review notes](../evals/retrieval_review.json) and [results](../evals/retrieval_results.json).

## Initial CCL study

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
cross-company benchmark. Answer replay reuses a draft only with the same evidence IDs, model
and prompt version and reruns validation. Raw passages, drafts, timings and API job results stay
in ignored local `artifacts/`; committed results contain source links, metrics and notes.


The live local persisted-job workflow also passed: a fresh, validated CCL answer used
hybrid retrieval and the next identical request returned the same cached answer. Source
PDF page 11 and its original link were preserved; financial comparisons remained off.
The 112-test suite, production build/secret scan and 44 Light/Dark/System browser
regression scenes passed.

### Quota migration verified — 31 October, 13:02 IST

The owner applied migration 0007. Live isolated checks confirmed that two batches of
two texts exceed a three-unit daily/minute allowance; audit reservations were removed.
The quota RPC remains server-only, and embedding-table security checks pass. Cached
CCL hybrid retrieval worked with zero provider calls; the deployed keyword job also
completed successfully. After the daily reset, one bounded 24-chunk resume test
advanced INFY from 264 to 288 of 1,125 chunks. This updates indexing progress, not the
frozen evaluation scores above. Production's semantic flag remains off.


## New-company validation after the quota reset

The subsequent GOKEX test began with **no existing corpus**. The generic NSE resolution
and link-discovery flow acquired a 254-page annual report and two original transcripts
(19 and 26 pages), stored the private source documents, activated the manifest and
scheduled embeddings automatically. No manual document links, prepared-company branch,
new model or production flag change was used.

The first business answer used keyword search with an indexing limitation. Once all
**711/711** chunks were embedded, the identical question produced a new hybrid answer
instead of reusing the preparing-state keyword result. Company filtering, original PDF
pages/links and private-result policies remained intact. CCL is still 694/694; INFY is
288/1,125. The verification/indexing processes have finished; this is not a continuously
running backfill service.

Three new positive questions and one negative were source-labelled, then evaluated
with the **already frozen CCL settings**. No tuning used GOKEX. The separate default
business smoke test was observed beforehand, so this is not a blinded study. Results
and reviewed output notes are in [new-company measurements](../evals/generic_retrieval_results.json)
and [source review](../evals/generic_retrieval_review.json).

| GOKEX measure, three positives | Matched keyword | Hybrid |
| --- | ---: | ---: |
| Reference-page Recall@5 | 0.667 | 0.833 |
| Reference-page Recall@10 | 0.833 | 0.833 |
| Reviewed validated-answer quality / 2 | 1.33 | 1.67 |
| Unsupported FY2030 question | Correct abstention | Correct abstention |
| Warmed retrieval median, 12 measurements/method | 647 ms | 1,771 ms |

Both methods correctly describe the apparel platform and overseas manufacturing
footprint, although the platform answers repeat themselves. Keyword's footprint
citation on PDF page 8 is a valid alternative outside the reference labels. The
hybrid tariff answer explains customer discounts net of supply-chain discounts;
keyword focuses on buyer pricing and omits supplier participation. Relevant material
exists in both contexts. This one-run quality difference includes generation choices
and conservative claim withholding; it is not causal proof that embeddings improve
answer accuracy.

The wider labelled set now has sixteen cases: nine executed across two companies
(seven positives, two negatives), with seven original INFY/POLYCAB cases still pending.
Across the seven executed positives, macro reference-page Recall@5 is **0.571 to 0.929**
and Recall@10 **0.857 to 0.929**; reviewed quality is **1.57 to 1.71 / 2**. Both negatives
abstain correctly. The pooled warmed medians are **495 ms versus 1,471 ms**, with 27
measurements per method from different times on the operator's connection. This remains
a small, assistant-reviewed check with curated references, not a market-wide benchmark.

Additional source-quality observations remain visible: one transcript index label is
Jun 2026 but its primary header says May 25; publication/reporting fields stay unknown.
A font control character caused both methods to lose one paraphrased quotation under
strict source-slice validation. A separate default-business answer included an excerpt
starting inside a word at an overlap boundary; its fact was checked against the full
primary page. Whole-word excerpts, cleaner attribution and less redundant generation
remain worthwhile improvements. Financial table comparisons remain disabled.

The production flag remains off. These results support a controlled trial on complete
indexes, while broader coverage and independent human review remain unfinished.

Reproduce the added check after the CCL collection/tuning commands above:

```powershell
.venv\Scripts\python scripts/evaluate_retrieval.py collect --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py score --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py answers --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py latency --symbols GOKEX
```
