# Build history

This timeline summarizes significant implementation decisions using dated commits and
source-review records. Dates are in IST. Git history preserves the full changes;
this narrative follows the application from dependency checks to the final interface.

## October 30, 2026

### Establishing the foundation

The initial design chose an attention inbox over a chat-first product: investors should
see actionable company developments, then inspect the evidence. React/TypeScript,
FastAPI and Supabase kept the stack small; Render supplied static/free API hosting,
and GitHub Actions would update sources independently of a sleeping web process.

Dependency work checked actual NSE prices/announcements, generic annual-report and
transcript discovery, page-aware extraction, Gemini access and Supabase FTS/vector/Storage.
Financial extraction preserved table candidates and metadata without enabling comparisons
from unvalidated cells. RLS/private-bucket probes established intended public/private
boundaries, and the frontend build was checked for privileged-key exposure.
The first foundation was committed as `26299a8`.

### One-company research, then Push/Pull

The first complete research pipeline resolved INFY, discovered primary links, stored
hash-versioned PDFs/pages, retrieved company-filtered keyword passages and produced
source-validated claims before expanding to POLYCAB and CCL. Persisted jobs, progress,
cache reuse and restart handling avoided a separate queue service. Narrative-column
interleaving was corrected while ambiguous financial-table numbers remained blocked.

The first working prototype (`00d1e2d`) added the 15-company watchlist, NSE RSS ingestion,
explainable categories, date windows, EOD price/volume alerts and source-to-research
navigation. Incomplete RSS and timestamp variants became explicit coverage states.
An early statement/evidence comparison distinguished guidance from a completed outcome;
reasoning-model latency led to a bounded smaller-model path rather than an invented verdict.
A dated public-only snapshot provided visibly historical recovery content.

### Source access and deployment constraints

The Virginia API could reach Supabase/Gemini but failed unfamiliar-company discovery.
Operator-only fixed-host probes and IPv4 testing isolated the issue without replacing
failed research with seeded results. A bounded Singapore service test completed genuinely
unprepared TCS research; HINDUNILVR later used the same route. The frontend switched to
Singapore only after successful source and browser checks (`7063fc2`, `b304a0d`).

A slow 361-page report also exposed PDF processing cost. Reusing PDFium for large native
text passes, while preserving financial layout/table extraction, reduced the measured
local extraction from about 60 seconds to 7. That measurement did not establish deployed
cold-start performance. Native-handle cleanup and progress reporting accompanied the change.

GitHub jobs were blocked before runner assignment by an account billing restriction,
even after public visibility. A Supabase Cron/pg_net/Vault fallback (`8a44624`) reused
the existing API, private singleton lease and source status rather than introducing a
paid scheduler. It separated dispatch acceptance from actual fetch completion.

## October 31, 2026

### Reliable sessions and scheduled recovery

The first real fallback run refreshed filings and 14 of 15 prices; a Yahoo rate limit
remained visible. Bounded retry recovered it, with manual and scheduled runs distinguished.
A later check caught a more serious issue: recent fetch timestamps accompanied older
sessions because the latest Yahoo close was null. Freshness checks were strengthened
around actual trading dates rather than treating successful transport as current data.

Exact-date NSE UDiFF recovery (`34c0cac`) validated EQ symbol, ISIN and source hash for
an incomplete latest returned bar. Invalid historical baselines, backward updates and
split-affected comparisons remained guarded. A genuine scheduled invocation then
recovered all 15 actual sessions. After GitHub billing recovery, CI and source sync ran
successfully on standard Ubuntu; both fallback schedules were deactivated before GitHub
scheduling resumed (`7aa6f54`), avoiding duplicate automatic ingestion.

### Themes and measured hybrid retrieval

Persistent Light/Dark/System themes used shared tokens and an early startup script to
avoid a wrong-theme flash (`ef3d47d`). Browser checks covered system changes, persistence,
focus/contrast and phone/desktop geometry.

Keyword retrieval was extended with direct Gemini embeddings, Supabase pgvector,
matched metadata filters, RRF, persistent vector caches and resumable indexing (`d877589`).
A real daily quota failure showed that individual texts inside a batch consumed the
allowance; accounting was corrected and foreground headroom reserved. A database
interruption proved checkpoint recovery instead of restarting the whole embedding job.

Source-labelled CCL evaluation caught an existing four-passages-per-document selector
cap. Both keyword and hybrid baselines received the fix before attributing gains to
semantics. Development-only tuning selected 30 candidates, k=10 and semantic weight 2.
GOKEX was then acquired through the generic pipeline and evaluated with frozen settings
(`4a3c17e`). Recall improved on this small set, with extra latency and limited/equal
answer-quality gains. Unsupported EBITDA added to a margin quote was caught in review
and guarded. Production rollout was selective: complete indexes could use hybrid;
partial INFY/POLYCAB retained keywords (`0653dcb`).

### Evidence-first and financial research

Contextual research (`a35bc64`) bound follow-ups to server-resolved claims/citations while
retrieving other documents. Repetition, later-evidence and perspective paths preserved
company context and exact passages. Unknown chronology abstained; later-source rules
were narrowed so they did not incorrectly constrain general follow-ups. Browser review
also fixed modal focus restoration.

Quarterly results (`e783cbe`) added generic primary-filing discovery, native cell geometry,
period/unit/basis preservation and Decimal QoQ/YoY calculations. POLYCAB and CCL validated
the first complete path. Wrapped headers were fixed so six-month values could not enter
quarterly comparisons; damaged native CCL figures were initially withheld. EBITDA stayed
reported-only. Financial figures and formula inputs reused the evidence drawer.

The research-experience pass (`879a409`) expanded multi-source explanations, separated
cached/prepared answering from serial acquisition, and exposed useful progress/timing.
It raised large-report bounds, added version-preserving bounded image agreement for
eligible quarterly cells, and recovered some CCL figures without guessing decimals.
All 15 watchlist companies yielded some usable financial data, with metric/basis gaps
retained. Management tracking moved from fragments/analyst questions to complete verified
management speech. Daily quota-bounded indexing maintenance reduced dependence on an
always-awake API.

## November 1, 2026

### Investor questions and financial interpretation

Real INFY, M&M, CCL, NTPC, SUNPHARMA and KPIT testing exposed missing answer aspects and
repeated quarterly render sections. Intent/aspect coverage, bounded focused retrieval
and one repair pass improved substance while explicitly withholding unsupported segment
contributions. Cached-result identity checks kept one financial section and preserved
basis selection (`5cd8f34`). Demand evidence and aggregate-profit wording received
focused follow-up corrections rather than wholesale prompt changes.

SUNPHARMA interpretation separated observed revenue/profit divergence from verified
cost/settlement disclosures. KPIT's missing range unit and incomplete target period
remained not assessable, not a manufactured numerical delivery gap.

### Coordinated workspace redesign

The shared layout (`abfdc76`) replaced oversized floating navigation and promotional
introductions with compact titles, desktop header/mobile safe-area navigation and retained
page state. System Status replaced the prominent development setup screen and gained
a return action. Filters, drafts, scroll and evidence context survived section switching.

Briefing (`bd626c2`, `490612d`, `739613d`) shifted from individual filing cards to compact
company/event views. One explanation, category/date, appropriate actions, official links
and optional evidence inspection replaced repeated text/nested cards. KPIT tenure and
NTPC/Reliance call-recording relationships were checked against originals. NTPC's common
PDF packet was split into distinct results, dividend and debt developments; arbitrary
summary truncation was removed without inventing incomplete source text.

Research (`5de6dc5`) gained company-name/alias/typo discovery, explicit ambiguous selection,
a vertical watchlist and four one-click workflows. Request-generation guards prevented
late overviews from overwriting selected results; company workspaces and accounting basis
were retained. Source details moved behind progressive disclosure while limitations
and evidence stayed accessible. Visual matrices reused real answers across themes.

## November 2, 2026

### Watchlist consistency and reliable identities

Portfolio became a compact sortable desktop table and mobile watchlist (`8928840`),
with shared methodology, genuine filing/EOD activity and primary Research actions.
The dark palette moved to charcoal surfaces and muted blue (`12c8eef`), reserving
financial green/red for meaningful status. Integrated testing found sticky quarterly
cells widening the mobile root page; containment fixed this while retaining local
table scrolling (`7ff9623`).

Intermittent NSE directory 403s revealed an unnecessary live dependency for already
known companies. Persistent verified snapshots, trusted stored identities, guarded
daily refresh and last-known-good fallback removed that blocker (`204788e`). Company
selection became more discoverable; generic split methodology moved out of every row.

Event review then adopted source-version receipts and event-level counts (`aa04e41`).
New/changed evidence becomes Updated since review; duplicates do not. Review state
stopped affecting sort order. Portfolio unusual-activity priority stayed distinct
from the chosen sort, and alert thresholds remained separate from filing-date filters.

### Production retrieval and numerical reliability

Production scope (`c86fcf9`, `1154a2d`) brought current quarterly PDFs into shared private
search/indexing, added conditional atomic vector writes and source-scope cache invalidation,
and distinguished no eligible documents from semantic failure. Existing RRF settings
were retained. V2RETAIL demonstrated generic quarterly acquisition and a hybrid follow-up.
The frozen CCL/GOKEX recall/latency rerun did not repeat generated-answer evaluation.

Verified numerical research (`6b8f7c4`) introduced metric recognition, conditional approved
calculations and source-complete reported/calculated/unavailable results. TMCV debt/equity
and V2RETAIL margin were checked against originals; TMCV/TMPV safeguards blocked inferred
historical recasts. Credit-rating classification also moved from substring detection
to agency/action context, avoiding incidental-word false positives.

Evidence controls became explicit panel-opening chips (`b333f76`). Reliability work
(`818097a`) separated invalid source references from temporary storage failures, retained
labelled saved evidence, and gated follow-ups on verification. A read-only verification
script reused existing caches/RLS/source checks without research POSTs or model calls.

## November 3, 2026

Research presentation (`31d4a89`) grouped same-result disclosed context under one heading
and qualification, with individual citations. General answer prose became selectable
rather than redundantly clickable; numerical evidence interactions stayed unchanged.
Targeted browser/build checks reused saved sources without backend regeneration.

The documentation/security pass (`406fd0e`) checked requirement coverage, public/private
boundaries, deployed revision/assets and repository credential exposure. Read-only
checks retained cold-start failures and skipped model operations explicitly rather than
claiming fresh generation. Source schedules remained distinguished from actual completion.

The subsequent documentation-only cleanup consolidated phase reports into seven technical
guides, shortened the public README, removed personal submission files and placed this
history in one oldest-to-newest timeline. No application behavior, data pipeline,
configuration or test logic changed.
