# Retrieval and AI evaluation

The studies below compare keyword retrieval with Gemini/pgvector/RRF on actual primary
documents. They are small engineering checks reviewed by the coding assistant, not
independent human assessments or representative Indian-equities benchmarks. Retrieval
recall, answer quality and latency are measured separately.

Labels and reviewable results:

- [Reference questions and PDF pages](../evals/retrieval_cases.json)
- [CCL measurements](../evals/retrieval_results.json) and [answer review](../evals/retrieval_review.json)
- [GOKEX measurements](../evals/generic_retrieval_results.json) and [answer review](../evals/generic_retrieval_review.json)

## Method and baseline correction

Recall@5/@10 measures curated reference PDF pages, not every relevant page in a report.
Chunks occupy ranking slots; duplicate reference pages count once. A different valid
source page may support a good answer without improving reference-page recall. Source
support and answer usefulness therefore require separate review.

An initial selector allowed only four passages per document. Queries restricted to
one report lost useful passages at ranks 5–8, producing reference-page Recall@5/@10
of 0.25 on the initial CCL set. An adaptive document cap fixed this for both keyword
and hybrid. That improvement must not be credited to embeddings. A matched keyword
arm controls for the candidate-budget/diversity correction.

Twelve development-only configurations varied branch candidates (30/60), RRF k (10/60)
and semantic weight (0.5/1/2). Two CCL development questions selected **30 candidates,
k=10, semantic weight=2**, within ten final passages and two per page. Two CCL positive
hold-outs and the later GOKEX cases did not select settings. Sixty candidates supplied
no extra reference-page gain. These are provisional settings chosen on very little data.

Generation used the same model, prompt and validation for both retrieval arms. Reviewed
quality is scored out of two after validation/withholding. It is a one-run qualitative
assessment, not proof that any difference was caused by retrieval.

## 31 October 2026: CCL development and hold-out

The complete corpus contained one annual report and two calls, 694 chunks. Four
answerable questions covered private-label manufacturing, cost-plus economics, expansion
location and coffee demand/product mix. An unsupported FY2030 audited-revenue question
checked abstention. Broader INFY/POLYCAB cases could not run because their indexes were
incomplete after the provider's individual-input daily limit was reached.

| Measure | Matched keyword | Hybrid |
| --- | ---: | ---: |
| Macro reference-page Recall@5 | 0.500 | 1.000 |
| Macro reference-page Recall@10 | 0.875 | 1.000 |
| Development Recall@5 / @10 | 0.500 / 0.750 | 1.000 / 1.000 |
| Hold-out Recall@5 / @10 | 0.500 / 1.000 | 1.000 / 1.000 |
| Reviewed validated-answer quality / 2 | 1.75 | 1.75 |
| Unsupported-question abstention | 1/1 | 1/1 |
| Warm median retrieval | 461 ms | 1,403 ms |

Warm timing used 15 alternating-order measurements per method, three repetitions of
five questions, actual database calls and cached query vectors. Ingestion/generation
were excluded; there were no embedding-provider calls during warm measurements.
The first collection pass mixed cached/uncached embeddings and a larger candidate
budget, so it is not a clean cold-cache baseline.

Both methods answered the expansion question after the selector fix. Keyword also
found valid private-label evidence outside the curated reference pages. A hybrid draft
added unchanged EBITDA to a margin quote; review caught the mismatch. A conservative
named-metric guard now withholds that claim and rejects similarly unsupported cached
answers. Another annual-table claim was withheld by the existing number guard.
Recall improved, but final reviewed answer quality was equal and warm retrieval added
about 0.94 seconds. Quotation presence alone did not settle management attribution.

## 31 October 2026: unfamiliar-company validation

GOKEX began without a corpus. The generic pipeline acquired a 254-page annual report
and two transcripts, answered with keyword retrieval during indexing, then produced
a hybrid answer once all 711 chunks were embedded. Completion invalidated the preparing-state
keyword cache. No prepared-company branch or manual document links were used.

Three positive questions and one unsupported question were source-labelled before
collecting their rankings. The CCL settings stayed frozen. A default business smoke
answer had already been observed, so this was not a blinded study.

| GOKEX measure | Matched keyword | Hybrid |
| --- | ---: | ---: |
| Reference-page Recall@5 | 0.667 | 0.833 |
| Reference-page Recall@10 | 0.833 | 0.833 |
| Reviewed validated-answer quality / 2 | 1.33 | 1.67 |
| Unsupported-question abstention | 1/1 | 1/1 |
| Warm median, 12 measurements per method | 647 ms | 1,771 ms |

The hybrid tariff answer covered customer discounts net of supply-chain discounts;
keyword omitted supplier participation despite relevant material in both contexts.
Generation choices and claim withholding contribute to that difference. Some valid
alternative pages did not count toward reference recall. Strict source-slice checking
also lost a paraphrase around a font control character. A transcript's discovery month
differed from its primary header; unverified date fields remained unknown.

Across the original seven positives, aggregate Recall@5 was 0.571 versus 0.929 and
Recall@10 0.857 versus 0.929. Reviewed quality was 1.57 versus 1.71/2, and both negatives
abstained. Seven labelled INFY/POLYCAB cases remained unexecuted. That subset must not
be presented as evaluation of every labelled company.

## 2 November 2026: frozen production-scope rerun

Current source versions were scored without retuning weights or repeating generated-answer
quality evaluation. Seven positive CCL/GOKEX cases were scored. Two unsupported questions
were retrieved but excluded from Recall, without claiming a new abstention-quality score.

| Retrieval | Recall@5 | Recall@10 | Warm median |
| --- | ---: | ---: | ---: |
| Matched keyword | 0.5714 | 0.8571 | 688 ms |
| Hybrid | 0.9286 | 0.9286 | 1,881 ms |

Timing used 27 measurements per method: nine questions, three alternating-order repeats,
stored query embeddings and zero embedding-provider calls. It includes workspace-to-Supabase
round trips, not just SQL execution, generation or a Render latency SLA. Some held-out
questions gain no Recall@10. Results justify retaining the settings for selective rollout,
not claiming universal superiority. Separate V2RETAIL production checks were not added
to the scored set after observing their answers.

## Reproduction and remaining work

These commands require server credentials and complete company indexes. They can use
Gemini quota and write ignored evaluation artifacts; do not run them as routine smoke tests.

```powershell
.venv\Scripts\python scripts/evaluate_retrieval.py collect --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py tune --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py answers --symbols CCL
.venv\Scripts\python scripts/evaluate_retrieval.py latency --symbols CCL
# New-company scoring reuses the CCL settings; do not tune on GOKEX:
.venv\Scripts\python scripts/evaluate_retrieval.py collect --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py score --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py answers --symbols GOKEX
.venv\Scripts\python scripts/evaluate_retrieval.py latency --symbols GOKEX
```

Collection refuses keyword substitution for unavailable hybrid and resumes completed
cases. Tuning refuses missing positive cases. Answer replay requires matching evidence,
model and prompt, then reruns validation. Raw passages/drafts/timings remain in ignored
`artifacts/retrieval/`; committed JSON preserves labels, metrics and review notes.
Process-local evaluation settings do not edit Render or `.env.local`.

Broader complete-index coverage, independent human review, multiple generation samples
and more financial/chronological questions remain needed. Financial-cell correctness
uses a separate [validated pathway](QUARTERLY_RESULTS.md). The [retrieval guide](HYBRID_RETRIEVAL.md)
explains production scope/fallback, and [reliability testing](EVALUATION.md) covers other workflows.
