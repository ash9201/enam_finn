# Submission draft

Subject: **ENAM - IIT screening - 2027**

Hi ENAM team,

I built FINN, a mobile-first attention inbox and primary-source research tool.

- Prototype: https://finn-web-yb14.onrender.com
- Repository: https://github.com/ash9201/enam_finn
- AI build history: [add the redacted conversation export or share links]
- Demo recording: [attach a short phone-sized walkthrough]

The prototype follows 15 NSE companies. It prioritises real exchange filings, collapses
routine notices, and applies configurable EOD price/volume rules. From a filing or a
company ticker, investors can ask for research grounded in annual reports and call
transcripts, with original-source links and PDF-page quotes. Three prepared companies
use the same discovery/extraction/retrieval pipeline as an unfamiliar ticker.

The narrative/evidence example puts an earlier management statement beside later call
evidence. It deliberately withholds a delivery verdict when a completed, comparable
target period is not established. This shows the distinction between reading management
and evaluating what the evidence can support.

Quarterly results add source-validated figures and deterministic QoQ/YoY changes,
with accounting-basis controls and evidence for each figure and calculation. POLYCAB
validates cleanly; CCL deliberately withholds damaged native cells. EBITDA stays
unavailable where the primary filing does not report it.

I used React/TypeScript, FastAPI, Supabase, and free Render hosting. PostgreSQL keyword
retrieval is complemented by a feature-flagged Gemini/pgvector/RRF implementation with
incremental indexing and keyword fallback. The small CCL study and a later unprepared
GOKEX check with frozen settings improve early reference-page recall, with a modest
observed answer-quality difference and higher latency. Production stays keyword-only
during controlled rollout. Gemini Flash-Lite handles ordinary work. The stronger model is bounded and
cached, with an explicitly recorded fallback when its free-tier service is unavailable.
GitHub Actions drives automatic source updates; its full filing scan and 15-company
price refresh were verified. A tested Supabase Cron fallback is retained but inactive.

Reliability choices include source hashes, page-level provenance, exact source-slice
citation checks, RLS/private PDFs, saved research, visible fetch failures, and a clearly
labelled recorded snapshot. Figures with unresolved periods, units, or accounting basis
do not become financial comparisons.

I left out trading, P&L, real-time prices, broad OCR, voice, and external notifications.
Next I would expand independently verified financial extraction and four-quarter
statement/outcome tracking, and retain hybrid retrieval only where tests show a benefit.
Frontend build and secret checks pass; regression and targeted checks cover 156 passing tests. Deployed
phone/desktop browser checks also pass. Free-hosting cold starts and upstream failures
remain visible.
When Yahoo omits a completed session's closing price, FINN checks NSE's exact-date
official daily file, validates the symbol/ISIN, and displays that source explicitly.
An older response cannot overwrite a newer saved trading session.

Best,
[Your name]

---
Before sending: verify the prototype on a phone/incognito session; ensure reviewers can
access the repository; include the actual build-history export and recording; remove
placeholders above. This file is a draft, not a sent email.

Technical acceptance: hosted CI and a real full-source GitHub run passed, and the
[scheduler switch](GITHUB_AUTOMATION.md) is complete. Supabase fallback schedules
are inactive. Live unfamiliar-ticker discovery passes on
Singapore and the frontend uses that API. Final manual items are the real-device
review, name/attachments, and the required redacted conversation export; see
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). This draft has not been sent.
