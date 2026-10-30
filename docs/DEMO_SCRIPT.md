# FINN demo: approximately 90 seconds

Open https://finn-web-yb14.onrender.com on a phone. Use a fresh browser session and
inspect the displayed source dates rather than expecting a particular alert forever.

| Time | Action | What it demonstrates |
| --- | --- | --- |
| 0–15 s | Open Briefing, inspect a price/volume signal and one filing. | Investor attention, completed-session dates, explainable priority and direct sources. |
| 15–30 s | Expand routine filings; switch 24 hours to seven days; adjust alert thresholds. | Useful Push controls and retained local preferences. |
| 30–55 s | Investigate INFY, POLYCAB or CCL. Open a claim's evidence drawer and its original PDF. | Concise Pull research, exact excerpt, page number, source link and honest metadata coverage. |
| 55–75 s | On INFY, inspect the earlier-statement/later-evidence panel and both citations. | Management narrative checked against evidence; incomplete target-period support yields “not yet assessable.” |
| 75–90 s | Ask a suggested question or enter an NSE ticker. Show progress if uncached. | Same generic discovery/retrieval pipeline; specific errors rather than invented answers. |

Prepared answers load independently of the API. A sleeping API can take about a
minute to wake; a first-company document load can take several minutes. Do not cut
out those delays and label a cached result as a new live discovery.

TCS and HINDUNILVR were genuine unprepared cloud tests when first ingested; both now
have saved corpora. They are useful examples of generalisation evidence, but entering
them again is a cache/reuse demonstration. For a genuinely new ticker, check that it
has not already been researched and allow the real acquisition to finish. Valid
tickers may lack accessible transcripts or exceed the bounded PDF limits; show the
specific coverage failure honestly.

If no recent filings fall within the current window, use the explicit seven-day
control. Preserve dates and never describe historical events as today's news.

Backup recording: `artifacts/demo/finn-phone-demo.webm`. Generate a new recording:

```powershell
$env:FINN_BROWSER_URL='https://finn-web-yb14.onrender.com'
python scripts/npm.py run record:demo
```

Browser emulation is not a physical-device test.
