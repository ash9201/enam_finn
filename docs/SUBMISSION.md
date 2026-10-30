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

I used React/TypeScript, FastAPI, Supabase, and free Render hosting. PostgreSQL keyword
retrieval ships first; pgvector fields and metadata are ready for a measured hybrid/RRF
extension. Gemini Flash-Lite handles ordinary work. The stronger model is bounded and
cached, with an explicitly recorded fallback when its free-tier service is unavailable.

Reliability choices include source hashes, page-level provenance, exact source-slice
citation checks, RLS/private PDFs, saved research, visible fetch failures, and a clearly
labelled recorded snapshot. Figures with unresolved periods, units, or accounting basis
do not become financial comparisons.

I left out trading, P&L, real-time prices, broad OCR, voice, and external notifications.
Next I would expand independently verified financial extraction and four-quarter
statement/outcome tracking, and retain hybrid retrieval only where tests show a benefit.

Best,
[Your name]

---
Before sending: verify the prototype on a phone/incognito session; ensure reviewers can
access the repository; include the actual build-history export and recording; remove
placeholders above. This file is a draft, not a sent email.

Current gate: complete the Supabase Cron deployment/acceptance check documented in
[SUPABASE_CRON.md](SUPABASE_CRON.md). Live unfamiliar-ticker discovery now passes on
Singapore and the frontend uses that API. GitHub hosted CI remains blocked by an
account-level billing lock; local tests pass. Disclose any remaining automation or
hosted-CI limitation before treating this as a final submission.
