# Working-prototype acceptance

**Hybrid production rollout (31 October):** enabled on the Singapore API. Fresh CCL
and cached GOKEX hybrid answers pass; incomplete INFY/POLYCAB use keyword fallback.
All 25 targeted hybrid tests and live quota-accounting audit pass. Backfills are
pending the next daily bulk allowance. [Current coverage and configuration](HYBRID_ROLLOUT.md).

**Quarterly results (31 October):** full regression 154 plus two targeted EBITDA
cases pass (156 total, including 27 financial cases). POLYCAB/CCL primary filings
validate the full results/evidence workflow,
with partial CCL cells and unreported EBITDA honestly withheld. Four affected
viewport/theme combinations pass contrast/overflow, basis, formula and evidence
checks, with one actual cross-document follow-up. Render's cached financial job and
live primary-source refresh also pass. [Details](QUARTERLY_RESULTS.md).

**Evidence-first research update (31 October):** 129 backend tests, production frontend
build, bundle credential scan, four real-API viewport/theme interaction checks and
44 theme scenes pass. CCL July→October cross-document research and zero-model
abstention with no later source are verified. POLYCAB history ingestion reaches two
reports/four calls. [Detailed evidence workflow and limits](EVIDENCE_WORKFLOW.md).
Earlier milestone counts and source failures below are historical records.

The deployment/dependency gate was verified on 30 October 2026. A reasoning-model timeout
passed a bounded minimal retry; later complex requests exposed repeated latency. The
working prototype therefore records actual model routing and uses a bounded fallback.

**Latest:** Singapore is now the frontend's deployed API. Deployed mobile/desktop
browser checks passed after the switch. Local tests: **87 passed**. Supabase Cron is
configured and passed a real full-source scheduled refresh: **15/15 prices**, completed
filings, correct schedules, current source timestamps, and denied anonymous/private
access. Earlier failures and the first transient rate limit below are retained as history.

**GitHub recovery:** after the user resolved the account issue, hosted CI and a full
source sync passed on standard Ubuntu runners. The source run refreshed 15/15 prices
with correct sessions and `github_actions` provenance. Both Supabase fallback schedules
are now verified inactive, with no in-flight fallback work. GitHub's source variable
is verified `true`; both workflows are active. See [scheduler switch](GITHUB_AUTOMATION.md).

## Verified behaviour

- One company (INFY) completed generic discovery → primary PDF extraction → Supabase
  persistence → company-filtered keyword retrieval → source-backed answer before scaling.
- POLYCAB and CCL used the same pipeline as previously unprepared companies; all three
  now have one annual report and two transcripts. No demo-company answer allowlist.
- The repeated INFY question reused its cached answer with **zero extra model calls**.
- A different free-text demand/growth question completed through the actual API job
  and model path with three valid, manually reviewed source-backed claims.
- Two-column narrative extraction and split-word PDF whitespace were tested against real
  reports. Original layout and source slices remain preserved; ambiguous numbers remain
  blocked rather than silently normalised into financial figures.
- The mock portfolio contains 15 directory-verified NSE companies, each with an actual
  completed-session price snapshot. Volume baseline excludes the current day; stock
  splits suppress misleading comparisons.
- Real portfolio filings are prioritised. Results notices/publications differ from
  actual results; scheduled auditor rotation is routine; unknown disclosures remain
  visible for review.
- RLS is enabled on all seven research tables. Anonymous access to source documents,
  pages, chunks, jobs, and model usage is denied. Published prepared results and intended
  portfolio metadata are read-only to the publishable key. Raw PDFs remain private.
- Live nonempty write probes against nonexistent portfolio rows were denied for all
  three market tables; anonymous reads succeeded. No real rows were altered.
- Chromium checks cover 390×844 and desktop viewports, real saved data, windows, routine
  expansion, persisted threshold preferences, 15 portfolio cards, source drawers,
  persisted research jobs, and an unknown ticker without another company's answer.
- A recorded snapshot contains only anonymously readable outputs and always carries a
  visible historical-data notice if live saved updates cannot be read.

## Narrative/evidence example

The prepared INFY example quotes earlier margin guidance and a later reported margin.
It is explicitly **not assessable as target delivery** because the excerpts do not
establish the same completed target period. Both statements resolve to actual call
passages and PDF pages. A smaller model produced the prepared example after deeper-model
timeouts; the actual model is recorded. No fictional stronger-model verdict is shown.

## Deployment notes

The first API request from the verifier after more than 15 idle minutes took **43.19
seconds** and returned HTTP 200. Other users may keep the API warm, so this is an
observed idle-request latency, not a guaranteed cold-start duration. The static frontend
and Supabase public reads work independently of that API wake-up.

The user resolved a browser-specific uBlock Origin block. App connection failures now
suggest checking site-specific blocking rules without weakening source access policies.

## Reproduce checks

Run `python -m pytest`, the frontend production build, the emitted-secret scan, and
`python scripts/npm.py run test:product` with local services running. Full results,
screenshots, and primary-source evidence live in ignored `artifacts/`; the covering
note draft is [SUBMISSION.md](SUBMISSION.md).

Semantic retrieval is implemented behind its rollout flag, with pgvector/RRF, private
embedding caches, resumable indexing and keyword fallback. The [CCL evaluation](HYBRID_EVALUATION.md)
records actual results and the input-quota limit; production remains keyword-only.
Comprehensive OCR, full historical
exchange coverage, financial-table comparisons, and a four-quarter tracker remain out.

Earlier foundation release checks: **64 tests passed**, production build and emitted-secret scan
passed; phone/desktop product and connection-browser checks passed. Empty windows
recover through an explicit seven-day action. Live DB boundaries were verified.

## Deployment history and earlier failures

The updated frontend/API deployed successfully. Product browser checks passed against
the actual Render frontend. A new, uncached question completed on Render with five
cited claims, verifying the deployed model and retrieval path over existing documents.

An unfamiliar TCS request failed during document discovery. Operator-only fixed-host
probes confirmed Screener connection failures from Render, with and without IPv4;
the NSE directory also timed out under the shorter diagnostic timeout. Google model
and Supabase connections worked. The same generic source pipeline worked locally for
previously unprepared POLYCAB/CCL. This is **not** a successful deployed unfamiliar-ticker
test. Source failures now name the dependency; no saved answer is substituted.

GitHub accepted the source workflow and the required secrets/variable were verified,
but push CI and workflow dispatch both ended in `startup_failure` with zero jobs. Actions
is enabled, all three workflow files register as active, and no runner/code executed.
Consequently automated updates and hosted CI are **not verified as working**. The exact
account/run banner and Render region have been supplied by the user: GitHub reports a
failed-payment/spending-limit restriction; Render is in Virginia. The user raised the
Actions budget to $1 but reiterated no intention to spend. Scheduled sync was therefore
temporarily disabled pending verification of free included usage; automatic hosted CI
is also temporarily disabled to avoid a potentially billable private runner. See the bounded
[source-access check](SOURCE_ACCESS_CHECK.md).

A 1.8 MB phone walkthrough is recorded at
`artifacts/demo/finn-phone-demo.webm`. Keep the above issues visible in the submission
writeup until fixed; a recording does not demonstrate live discovery or automation.

### Follow-up: public GitHub and Singapore

The user made the repository public and restored the paid Actions budget to $0. Both
workflows were retried using only `ubuntu-latest`. Jobs now register, but GitHub assigns
no runner and reports: "The job was not started because your account is locked due to
a billing issue." This remains an account-level gate. CI is re-enabled, while the
scheduled-source variable remains off until a real source job succeeds. A support
draft is available locally at `artifacts/support/github-actions-account-lock.md`; it
has not been sent.

Singapore can reach Screener. A completely unprepared TCS request completed live:
one 361-page annual report, two transcripts, retrieval, and three verified claims.
No local TCS corpus was seeded. The first run was interrupted by a deployment; a
stable-deployment retry succeeded. The existing frontend/Virginia API is retained
until the verified endpoint can be switched and browser-tested.

The first TCS load exposed slow large-PDF extraction on free CPU. A local full-parser
benchmark improved from 59.95 seconds / 260 MB peak working set to 7.09 seconds / 164 MB
using native text extraction plus aligned financial-page/table processing. Both read
all 361 pages from the same original PDF, and all table candidates remain unvalidated.
These are local measurements, not a claimed cloud latency. Cold research on another
unprepared ticker is the next deployment check.


### Second live company and fresh source data

After the optimized parser deployed to Singapore, HINDUNILVR was tested as another
unprepared company from a different sector. It completed live discovery, a 246-page
annual report, two transcripts and two cited claims in **173.2 seconds**, with
`cached=false`. Its quotes were inspected; no numerical table comparisons were made.
TCS had previously completed the same live path with three supported claims. These
are separate-company tests; 173 seconds is not a controlled speedup measurement.

The Singapore API also passed the actual frontend-origin POST preflight and denied
an unrelated origin/operator access without the server key. The user has been asked
to update the static frontend API URL; the Virginia service is retained until browser
verification of that change.

A local manual source refresh completed successfully while GitHub remained locked:
15/15 EOD snapshots for **30 October 2026**, 19 portfolio filings from 2,158 feed items,
no unrecognised timestamps. Its execution origin is recorded as `local_manual` with
`automation_verified=false`; this is not a passed GitHub source-sync run.

### Singapore switch and Cron fallback

The deployed frontend JavaScript and local canonical API setting both reference
Singapore. Product browser tests passed against that deployment, including real
persisted jobs, citations, mobile/desktop layout, settings, missing-ticker handling,
and the explicitly labelled offline snapshot.

The user approved Supabase Cron because GitHub remains account-locked. Added the
private authenticated endpoint, cross-service database lease, serial worker, separate
source outcomes, Vault-backed dispatch, and expected half-hour/EOD schedules. Five
new tests cover denied access, duplicate/busy requests, actual worker submission and
independent source failures. SQL setup and scheduled-fetch verification are still
required; implementation is not being counted as working automation yet.

### First actual Cron execution (31 October IST)

The temporary self-removing schedule ran at 01:12 IST. Vault/pg_net dispatch succeeded,
the API woke and accepted work at 01:12:45, and actual fetching finished at 01:13:06.
Both regular schedules are active; private job RLS and anonymous read/write/function
denials pass. The completed NSE feed contained one genuine nonportfolio disclosure,
matching a separate local read after the feed's date rollover. Saved earlier filings
were preserved. A regular half-hour invocation is also monitored independently.

Yahoo rate-limited APLAPOLLO; 14 other prices refreshed, and the run correctly remained
partial. Its old price retained its date and an explicit fetch error. A separate
cloud-operator retry subsequently refreshed all 15; original scheduled failure and
manual recovery reports are preserved separately under `artifacts/release/`.

Added one bounded rate-limit retry and recovery of overdue/partial EOD work on later
announcement ticks. Nine additional tests cover retry exhaustion, market cutoff,
weekends, Monday before/after close, and preserving operator-requested mode. No
financial data, source provenance, or execution origin is fabricated to pass acceptance.

### Full scheduled acceptance passed (31 October IST)

Cron job 4 dispatched at **03:23 IST**; the API finished at **03:23:18 IST**. Its origin
is `supabase_cron`, mode `all`, state `completed`. All 15 prices refreshed with no
failed symbols. The announcement feed had two valid entries and zero portfolio
matches in its current window; earlier stored filings were preserved. Both source
statuses were completed with actual automation metadata. This first check validated
fetch completion rather than the underlying session dates; the follow-up below
documents the discovered gap and subsequent correction.

`scripts/verify_cron.py` passed access, schedule, actual dispatch, HTTP acceptance,
completion and freshness checks. Private job RLS is enabled; anonymous reads, writes,
schedule diagnostics and lease-function execution are denied. The temporary check
removed itself, leaving only the two intended schedules. Several regular half-hour
announcement jobs have independently succeeded. GitHub source scheduling stays off.

The initial partial scheduled run and successful operator recovery remain separate
artifacts; the acceptance result is a subsequent real scheduler run, not relabelled
manual activity. Hosted GitHub CI remains account-restricted; local tests pass.

### Session-date validation follow-up

The release export exposed a gap in that initial check: it had verified recent fetch
timestamps, while Yahoo's latest 30 October row had a volume but a null close. Dropping
that row returned 29 October quotes and had replaced newer saved sessions. This was
not accepted as current data. Restored the original verified 30 October snapshot with
explicit failed-refresh markers, preserved before/after evidence, and marked the source
failed so the existing overdue-EOD scheduler will retry it.

The adapter now validates the latest bar, uses only the matching official NSE daily
archive (date, EQ series, symbol, ISIN, finite values, size bounds), and preserves its
source URL/hash. It never substitutes an older bar silently. Prior history is still
Yahoo and is labelled separately; missing comparison-window bars block calculation.
Older responses cannot overwrite newer stored dates. All 15 official NSE rows were
verified locally without seeding cloud quote records. Cloud scheduled recovery and
the final price-source browser result are recorded below.

A real call-notice review also corrected an earnings-discussion schedule previously
described as available commentary; original filing sources and dates were preserved.
See [focused evaluation](EVALUATION.md) for the bounded review and remaining limits.

### Regular scheduled primary-source recovery passed

At **03:47 IST on 31 October**, the ordinary announcement tick detected the failed
EOD status, requested mode `all`, and finished at **03:47:33 IST**. This was the regular
schedule, not an operator call or another temporary SQL test. The Singapore API
downloaded the official 30 October NSE archive and recovered all **15/15** completed
session bars. All have matching source provenance, 30 October dates, and no refresh
errors. No local quote corpus was seeded to make this cloud test pass.

The strengthened verifier passes access, intended schedules, actual dispatch/HTTP
acceptance, completion, freshness and price-session integrity. The dated fallback
was then exported from anonymous-readable outputs. Phone/desktop browser checks cover
both the genuine failed-refresh labels and the recovered session/source display.
