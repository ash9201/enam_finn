# Release and submission checklist

Verified on **31 October 2026 (IST)**. This records a working prototype; it does not
claim complete financial-document coverage or an assessment submission already sent.

## Technical acceptance

- [x] Public frontend uses the Singapore API; public saved content works independently.
- [x] Fifteen-company portfolio with real EOD snapshots and exchange filings.
- [x] Completed-session price/volume arithmetic, configurable rules and visible failures.
- [x] Three prepared companies use the generic primary-document pipeline.
- [x] Initially unprepared TCS and HINDUNILVR completed genuine cloud acquisition/answers.
- [x] Source quotes, original PDFs, page metadata, conservative financial-number guards.
- [x] INFY narrative/evidence example with citations and a defensible abstention.
- [x] Private PDFs/source text/jobs remain protected; anonymous writes are denied.
- [x] Real Supabase Cron dispatch completed filings plus 15/15 EOD refreshes.
- [x] Temporary acceptance schedule removed; both Supabase fallback schedules inactive.
- [x] GitHub automatic source workflow enabled after fallback deactivation was verified.
- [x] Eighty-seven local tests pass; deployed browser connection/product checks passed.
- [x] Missing latest daily bars recover from exact-date NSE records, with visible provenance.
- [x] Older session responses cannot overwrite newer saved records; failed refreshes stay visible.
- [x] GitHub-hosted CI: 87 tests, frontend production build and secret scan passed.
- [x] GitHub source workflow: actual filing sync and 15/15 prices passed with correct dates.

## Final manual items

- [ ] Open the actual link on a physical phone, preferably in a fresh/private session.
- [ ] Export/share the actual AI coding conversation history required by the brief.
      Redact credentials and private SQL. `BUILD_HISTORY.md` supplements this export.
- [ ] Add your name and actual history/recording attachments to `SUBMISSION.md`.
- [ ] Review the recording; keep the original dates and cache labels visible.
- [ ] Submit to `assessment@enam.com`, subject `ENAM - IIT screening - 2027`, by the
      stated Sunday, 1 November deadline. Target the morning IST; no cutoff time was given.

No email has been sent by the coding agent. The covering note is reviewable before sending.

## Evidence and recovery

- `artifacts/release/supabase-cron-verification.json`: current read-only verification.
- Timestamped Cron reports preserve each check; the first partial run/operator recovery
  are separate files rather than rewritten successes.
- `artifacts/product-browser/`: real product checks/screenshots.
- `artifacts/milestone-0/browser/`: real API/cache browser connection checks.
- `artifacts/price-browser/`: actual failed-refresh and recovered-session/source checks.
- `artifacts/demo/finn-phone-demo.webm`: backup walkthrough.
- `frontend/public/recorded-snapshot.json`: explicitly dated, anonymous-readable data only.

If sources fail, show their actual failure and original data dates. If the API sleeps,
saved public content remains useful. Never publish `.env.local`, private configuration
SQL, raw private research records, or credentials with the submission.
