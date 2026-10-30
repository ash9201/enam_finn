# Working-prototype acceptance

The deployment/dependency gate was verified on 30 October 2026. A reasoning-model timeout
passed a bounded minimal retry; later complex requests exposed repeated latency. The
working prototype therefore records actual model routing and uses a bounded fallback.

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

Semantic retrieval remains a measured follow-up, not a claimed feature. pgvector and
model/dimension metadata are reserved in Supabase. Comprehensive OCR, full historical
exchange coverage, financial-table comparisons, and a four-quarter tracker remain out.

Local release checks: **61 tests passed**, production build and emitted-secret scan
passed; phone/desktop product and connection-browser checks passed. Empty windows
recover through an explicit seven-day action. Live DB boundaries were verified.

## Current external deployment issues — not a final submission gate pass

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
account/run banner and Render region have been requested from the user.

A 1.8 MB phone walkthrough is recorded at
`artifacts/demo/finn-phone-demo.webm`. Keep the above issues visible in the submission
writeup until fixed; a recording does not demonstrate live discovery or automation.
