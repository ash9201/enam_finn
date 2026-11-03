# Final submission checklist - 3 November 2026

The four-page `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf` and three-page
`2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf` were accessible and read locally.
They are deliberately excluded from the public repository. The PDF's original
deadline is 1 November; the owner confirmed an extension to **3 November EOD**.
That extension is owner-reported correspondence, not independently verified email.

## Assignment requirements and deliverables

| Requirement | Status / evidence |
| --- | --- |
| Working mobile-first Push and Pull prototype | Implemented: Briefing, Research and Portfolio; deployed responsive web; light/dark and desktop/mobile evidence checks. |
| Mock 15-20 NSE/BSE-listed companies, varied sectors/sizes | 15 verified NSE identities across IT, consumer, finance, industrial, power, pharma and other sectors. Live storage contains all 15. |
| EOD portfolio prices and volumes | Real saved Yahoo/NSE data, completed-session guards, previous-20-session volume baseline, configurable thresholds, dated sources/errors. |
| Exchange announcements/filings | Scheduled NSE RSS capture, classification, material/routine priority, event grouping and intact original sources. BSE hosts documents; a complete second BSE feed is not claimed. |
| Annual reports and earnings-call transcripts | Original primary PDFs, page-aware storage/retrieval and cited company-scoped research. Screener is a link index only. |
| A handful of research examples | INFY, POLYCAB and CCL published prepared-answer GETs checked; company-specific financial and management examples documented. |
| Generic engine beyond the demo set | Same directory/discovery/ingestion/retrieval path; earlier real TCS/HINDUNILVR/GOKEX acquisition verified in acceptance history. No new acquisition/model run during this readiness pass. |
| Primary-source-only Pull analysis | Source/claim/company binding, stored-quote/page/version verification, financial validation and explicit abstention. No broker/news/model-memory conclusions. |
| Deployed prototype and GitHub repository | Public website/API and public `main` repository checked; final revision/build verified after the documentation push. |
| Actual AI coding/LLM conversations | Owner has verified Markdown export from VS Code. Attach that export separately; it has not been recreated by the agent. Build-history summary is supplementary. |
| Short covering writeup | Updated reviewable [covering-note draft](SUBMISSION.md), including decisions, omissions and next steps. Owner must add their name/history attachment and send it. |

The glossary taxonomy, eight research sections, incoming-person biography and
four-quarter worked example are illustrative, not compulsory features. FINN implements
in-app scheduled alerts, selected financial analysis and statement-level management
tracking. It deliberately omits external notification delivery, biographies and a
complete four-quarter guidance scoreboard. These are scoped choices, not hidden gaps.

## Final technical and security evidence

- Read-only backend checks: **19 PASS / 0 FAIL / 2 SKIP**, with a 75-second cold-start
  allowance. The first default 20-second liveness probe timed out after idle time;
  its failure was retained rather than relabelled as success.
- The two live SKIPs are TMCV's absent current **public prepared-answer** cache
  (private numerical caches/evidence were verified), and deliberately uncalled live
  Gemini generation/semantic ranking. No ingestion, backfill or model evaluation ran.
- Relevant local backend subset: **184 passing tests**. Last full hosted CI: **336**.
  Production frontend build, company-search tests and local/deployed secret scans pass.
  UI evidence controls were checked on desktop/mobile in both themes on the current
  application-code release; current readiness uses a short read-only page smoke check.
- Repository was public, unarchived, default branch `main`; pre-final application
  revision was `31d4a89`. Final report identifies the subsequently deployed documentation commit.
- Security scan: **50 pre-finalisation reachable commits / 611 unique blobs / 7.8 MB**,
  using actual configured private values plus common API/token/service-role JWT/private-key
  formats; no findings. Dedicated gitleaks/trufflehog binaries were unavailable.
- Only placeholder `.env.example` is tracked. Actual env files, private artifacts,
  local toolchains, downloaded PDFs and build output are ignored. No history rewrite
  or force-push was performed. A bounded scan cannot prove absence of every encoded secret.
- Anonymous private-table/unpublished-answer reads are denied; RLS audit passes.
  No user authentication is implemented: possession of job/research identifiers allows
  associated API reads. Public financial documents are the intended demo content.

## Current operations (dated observation, not permanent guarantees)

- Source/embedding workflows have successful scheduled runs on `main`; public repo
  uses standard Ubuntu runners. Filings: minutes 17/47 UTC; prices: weekdays 12:45 UTC
  (18:15 IST); bounded indexing: daily 08:45 UTC (14:15 IST). GitHub can delay starts.
- Live source rows report completed `github_actions` runs; announcements were last
  checked 3 November, with capture beginning 30 October. Saved EOD dates remain visible.
  Specifically, the last completed filing scan was 08:09 IST at the 14:25 IST check.
  Both workflows are active, but on-time half-hour delivery was not observed. A manual
  source-workflow dispatch can refresh filings before a demo; this pass did not start
  ingestion or change scheduling merely to hide stale completion times.
- Both Supabase fallback schedules are **inactive**, confirmed through the read-only
  server status function. Their setup SQL must not be rerun while GitHub scheduling is active.
- Current semantic inventory: **3,299 / 20,028 chunks**, **17 / 75 documents**, **21
  collected companies**. CCL/GOKEX/V2RETAIL are complete; other companies use keywords.
- Owner confirmed Render API Free / Render static frontend / Supabase Free / Gemini
  free quota on 3 November. Billing dashboards are not accessible to the agent.
- Free Render API idle sleep/wake is expected. The static frontend/public saved data
  remain separately available; external sources, provider quotas and incomplete reports
  can limit an otherwise working prototype.

## Owner's remaining submission actions

- [ ] Open the deployed website on a physical phone/private browser; automated Chromium
      emulation is not an independent physical iOS/Safari test.
- [ ] Attach the already-exported AI conversation Markdown, after credential/private
      material redaction; the agent did not recreate or re-export it.
- [ ] Add your name and actual attachment/share-link references to the covering note.
- [ ] Optionally attach a reviewed current demo recording. A recording is backup,
      not a mandatory replacement for the working website. Older local recordings
      may show earlier UI/data; retain visible dates/cache labels.
- [ ] Email `assessment@enam.com` with subject **ENAM - IIT screening - 2027**, before
      the owner-confirmed **3 November EOD** extension, and confirm successful delivery.

No known code/deployment blocker remains after the listed checks. Email delivery,
personal attachments and final physical-device review remain outside the repository.
No email has been sent by the coding agent. See [README](../README.md) for the evaluator
entry point and [deployment checks](DEPLOYMENT.md#pre-submission-sanity-check) for exact commands.
