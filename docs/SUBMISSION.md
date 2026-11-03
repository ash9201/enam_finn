# Covering email draft - owner review required

To: **assessment@enam.com**

Subject: **ENAM - IIT screening - 2027**

Hi ENAM team,

Please find my FINN submission for the AI Engineer Build Challenge:

- Prototype: https://finn-web-yb14.onrender.com
- Repository: https://github.com/ash9201/enam_finn
- AI build history: **[attach the redacted Markdown conversation export / insert its share link]**
- Optional demo backup: **[attach/link only if including a reviewed recording]**

FINN is an investor attention inbox with evidence-backed company research. Briefing
prioritises exchange announcements across a 15-company NSE watchlist, retains routine
filings and applies configurable EOD price/volume rules. Portfolio makes company activity
and dated share prices easy to compare without inventing investment returns.

Research uses original annual reports, call transcripts and quarterly filings. Evidence
buttons reveal source passages/pages and support contextual investigation across documents.
Quarterly comparisons and common numerical questions use validated figures and deterministic
arithmetic; missing or incompatible data remains unavailable. Management-statement tracking
separates repetition, progress and outcomes rather than forcing a delivery verdict.

I chose React/TypeScript, FastAPI and Supabase, with Render hosting and GitHub Actions
updates. Company-filtered PostgreSQL keyword search combines with Gemini/pgvector/RRF
only when a company's index is complete. Partial indexing, free-tier quotas and source
failures retain keyword research and explicit limitations. Hash/version-aware caches,
private source storage and bounded model use keep the implementation focused and economical.
Screener supplies primary-document links, not secondary research conclusions.

I deliberately left out trading/P&L, live prices, broad OCR, biographies, external
notifications and a full four-quarter guidance dashboard. Next I would broaden independently
verified extraction and longitudinal management analysis, measuring retrieval benefits
before increasing complexity. The README explains actual coverage, schedules and limits.

The responsive demo, builds and regression checks pass. The Free Render API can need
about a minute to wake after idle time; the static frontend and saved data are separate.
Please allow the first API request to wake it and retry if necessary.

Best,

**[Your name]**

---

This draft has not been sent. Before sending, remove unused optional lines, replace
placeholders, attach the **already-exported** and redacted conversation history, and
check the link on a physical phone. Do not attach private `.env`/SQL/artifact dumps.
The owner confirmed an extension to **3 November 2026 EOD**; the original PDF says
1 November. See the [final checklist](RELEASE_CHECKLIST.md). No final delivery is implied
by a successful GitHub push.
