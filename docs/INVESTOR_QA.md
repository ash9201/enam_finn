# Investor QA fixes - 1 November 2026

This is a targeted follow-up to the owner's deployed INFY, M&M, CCL, NTPC,
SUNPHARMA and KPITTECH testing. React/FastAPI/Supabase, the evidence contract,
source acquisition, deployment and semantic rollout flag remain in use. No migration,
dependency, paid service, agent framework or new notification workflow is required.

## Results rendering and navigation

Repeatedly opening the already-active cached NTPC results reproduced the reported
problem: one answer panel accumulated three financial sections, leaving stale controls.
The quarterly shortcut and completed-job handler now retain the active answer when
its canonical ID, generation, source-check and presentation versions are identical.
A genuinely different generation or presentation gets
its own render boundary. The test watches the DOM throughout repeated opening,
typing, basis switching and completion of a cached request: maximum one results section.

NTPC contains verified data for both bases. Consolidated PBT remains unverified;
standalone PBT has three usable quarters. Switching updates the pressed button,
table identity, figures, missing cells, calculations and interpretation. Unsupported
bases, such as M&M standalone in current coverage, have a disabled control and an
explicit explanation. SUNPHARMA's existing figures on both bases are preserved.

Research now reserves a separate navigation row below the scrolling content. The
navigation keeps its existing appearance but does not float over figures. Tests check
the content/navigation bounds at the top, middle and end of scrolling.

## Answer intent and evidence selection

`grounded-analysis-v5.8-intent-coverage` adds deterministic investor-aspect detection
and at most four focused keyword searches. The original company/document/date/metadata
filters are forwarded. The main hybrid query, embedding model and evaluated RRF
settings (k=10, semantic weight=2) are unchanged. Selection reserves evidence across
aspects within the existing ten-passage budget. Focused-search failures preserve the
base search and are recorded rather than presented as no evidence.

The existing generation call uses a required structured field per requested aspect,
flattened into the same claims/citations response. This is an answer plan in one
call, not another planning agent. A single bounded repair can address still-missing
aspects from the same evidence; numerical contributions are never manufactured by a
repair. Supported claims are ordered by the requested subject. Unanswered parts get
a specific coverage message instead of silently disappearing.

Business-model retrieval prioritises actual services, customers and contract mechanics.
Commercial passages can be isolated as exact contiguous excerpts from accounting-heavy
pages; the original text remains unchanged for validation and evidence inspection.
Revenue recognition, principal/agent tests and unbilled-accounting sentences do not
replace an explanation of how customers pay. Recognition as an industry leader is
not mistakenly classified as accounting.

Customer demand stays one demand topic rather than adding an unrequested customer
profile. Direct evidence of returning or additional contracts can establish demand;
contract types alone cannot. This small correction followed a fresh production
request and invalidates older answer-plan caches through the prompt version.
Current-demand supplements prefer transcripts when no source-kind filter was supplied;
the main retrieval still includes reports. Explicit source filters remain in force.
As with other questions, a requested aspect can remain unverified after the bounded
repair; the UI reports that limitation rather than marking coverage as complete.

Coverage checks distinguish customer sectors from services offered, volume guidance
from demand evidence, and EBITDA guidance from profitability drivers. These are
bounded relevance checks, not a proof of semantic entailment. Primary quotes and
financial-table guards remain necessary; the reviewed cases were inspected manually.

## Actual research checks

| Owner's question | Before | Reviewed result |
| --- | --- | --- |
| INFY business model, services, customers and revenue | Four points included principal/agent and recognition detail | Three focused points: technology/engineering/digital services, enterprise sectors, and time-and-material/unit-of-work/fixed-price/fixed-timeframe contracts. All three aspects covered; 7.89 s prepared generation. |
| CCL profitability, demand, capacity and future growth | Two points, with demand and growth effectively omitted | Five points cover cost-plus/mix, demand preferences, capacity headroom and management guidance. All four aspects covered; 18.23 s prepared generation including bounded repair where needed. |
| M&M segments and contributions | Qualitative segment descriptions without a contribution limitation | Group segments and operating/holding roles remain explained. Numeric segment contributions were searched but not verified with compatible period/basis. The answer states this gap explicitly. 9.86 s prepared generation. |

These initial v5.7 observations use prepared corpora, not a
statistical latency benchmark. One malformed model response was rejected during
development. Intermediate candidates were not published; no historical answer was
silently substituted for a failed request. M&M numerical segment contributions remain
a real limitation: raw segment tables are not approved simply because retrieval finds
them. Generic ingestion and answering remain available beyond these test companies.

## Concrete management comparison

The reviewed CCL reaffirmation is preserved, including its primary sources, chronology
and distinction between guidance and delivered results. KPIT's existing verified pair
is decorated deterministically from exact reported metric phrases, without another
selection/model call. It now states:

- Earlier FY27 EBITDA range: **20.5 to 21.2**, with the unit explicitly missing.
- Later Q1 FY27 call: EBITDA **17.2%**, EBIT **12.3%**, PAT **INR 1.17 billion**.
- The missing range unit and comparable completed full-period outcome prevent a
  numerical target gap or delivery conclusion. The verdict remains not yet assessable.

The statements keep the original parent/citation IDs, roles, dates and quotes. Published
presentations are explicitly updated after review; source generation/check dates are
retained. No PAT amount is used as an EBITDA outcome, no period is inferred from an
index month, and no fresh verdict logic weakens existing safeguards.

## Financial performance interpretation

The results view adds short basis-specific observations using only approved cells and
existing Decimal changes. It highlights revenue/profit divergence without guessing
causes, avoids invalid percentages and links to the exact figures. Repeated identical
directional patterns do not produce repetitive commentary.

SUNPHARMA consolidated YoY illustrates the observation: Revenue +11.88%, PBT -24.19%,
PAT -36.16%. Standalone has a different YoY pattern and its own QoQ divergence; it does
not inherit consolidated commentary. Native statement values/definitions are unchanged.

The previous financial extraction stored selected statement pages but omitted notes.
An additive pass now preserves missing native pages from the same hash-checked private
PDF, bounded to 200 pages. Existing pages/chunks are not replaced, and quarterly
documents remain outside the annual-report/transcript vector manifest.

Conservative direct-disclosure rules can attach up to two qualitative notes with an
explicit matching quarter and an accounting basis established by approved statement
anchors. SUNPHARMA PDF p.16 supplies current-quarter acquisition/transaction costs and
a litigation settlement. Exact paragraphs remain inspectable; their raw monetary text
is not promoted into newly approved numerical figures. This identifies disclosed
items, not a complete attribution of the profit change. Unknown dates/bases, unsupported
categories, scans or unavailable text leave a clear unverified-cause caveat.

## Verification and operations

- **190 backend tests passed** in the final regression. Targeted tests were used during
  implementation; unrelated backend tests were not repeated per theme.
- TypeScript/Vite production build and privileged-credential bundle scan passed.
- Four affected browser scenes cover NTPC phone/light and desktop/dark, SUNPHARMA
  phone/dark and desktop/light. Repeated shortcuts, typing, both basis views, a real
  cached API request/evidence, unavailable M&M standalone, DOM uniqueness, scrolling
  bounds, no overflow and no page errors pass.
- Reviewed input/output artifacts and the reproduced failure capture are ignored under
  `artifacts/targeted-fixes` and `artifacts/investor-qa-browser`; no credentials are exported.

Reproduce with local services and existing credentials:

```powershell
$env:FINN_ENABLE_SEMANTIC_SEARCH='true'
.\.venv\Scripts\python.exe scripts/verify_investor_qa.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/npm.py run build
```

The verifier generates real-source review artifacts and defaults to private results.
Use `--publish` only for reviewed prepared outputs. It updates presentation metadata
without changing original financial cells, source dates or comparison verdicts.
No Render environment changes are needed; the normal main-branch deployment is used.
