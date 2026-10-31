# Focused reliability review

This is a small manual review backed by targeted regression tests, not a measured
accuracy score or an exhaustive benchmark. Existing live-source outputs supplied the cases.

| Case | Expected behaviour | Evidence |
| --- | --- | --- |
| Actual results versus meeting/newspaper notice | Prioritise results; keep notices accessible with honest wording. | Real portfolio filing review and classification tests. |
| Tata Steel scheduled earnings discussion | A meeting notice does not establish that management commentary is already available. | Corrected the stored category/reason without changing its source/date; added the actual description to a test. |
| Mandatory auditor rotation | Distinguish routine rotation from a substantive governance change. | Real Sun Pharma disclosure review and regression test. |
| Unclear “Updates” or security-cover filing | Remain visible and explicitly unclassified rather than inventing a material event. | Review of the actual saved filing descriptions. |
| Yahoo rate limit | One bounded retry; persistent failure retains dated saved data with a failure marker. | Real first scheduled partial run, separate operator recovery, and retry tests. |
| Latest daily bar has volume but a missing close | Do not skip the session and call older data current. Recover only from the matching NSE daily file or fail visibly. | Actual 30 October Yahoo response and dated NSE EQ record, date/ISIN/hash tests. |
| Older response after a newer saved session | Preserve the newer saved session and report failed refresh. | Regression test and saved operational before/after evidence. |
| Missing historical baseline bar | Do not substitute an earlier trading session into the 20-session comparison. | Financial arithmetic/coverage test. |
| Guidance versus later quarterly margin | Withhold delivery verdict without the same completed target period. | INFY's two original transcript quotes and conservative comparison tests. |
| Invalid ticker/missing sources/unavailable model | Specific failure or abstention, never another company's answer. | Generic-resolution, source/model failure and deployed browser tests. |

Source-slice validation checks that a cited excerpt exists. It does not prove that
every paraphrase is correct, that the source is complete, or that an investor should
act on a claim. Keep manually reviewing important interpretations and financial bases.

The prepared examples use a small number of concise qualitative claims. Detailed
financial-table comparisons remain disabled where periods, units or accounting basis
are unresolved. The subsequent [hybrid retrieval evaluation](HYBRID_EVALUATION.md)
compares keyword and semantic/RRF retrieval, reports the corrected baseline and actual
quota constraint, and keeps answer-quality findings separate from reference-page recall.
