# SEC EDGAR Real-Data Collection Validation — November 6, 2026

**Scope:** Three *small, user-executed live SEC collection runs* using News2Market on a local Mac, as supplied in local `sec_collection_audit.json`, `sec_data_quality_report.md`, and (for AAPL/GOOGL) `sec_filings.csv`. The NVIDIA run also had a `research_audit.json`. This document records **observed extraction quality, not a market return study or an independently reproduced live benchmark**.

## Reproduction and provenance

- Source: SEC EDGAR `data.sec.gov` submissions API and selected official primary documents at `www.sec.gov` via the local research CLI.
- Issuers: NVDA (CIK `0001045810`), AAPL (`0000320193`), GOOGL/Alphabet (`0001652044`). Each submissions response matched the requested CIK.
- Selection: up to five most recent matching 8-K / 10-Q / 10-K filings in the **2026-01-01 through 2026-11-05** filing-date window, from the API's recent submissions list, not a random or comprehensive historical sample.
- Acquisition mode: `--fetch-bodies` enabled; **6 SEC HTTP requests per issuer** (18 total). Each run reported a genuine `data.sec.gov API` source and no requirement to bypass rate limits. This evidence is supplied from user-run local audits, not independently captured by this repository's CI.
- Source data and full extracted texts are not republished here. Any future raw data release must comply with relevant source terms.

## Cross-company observations

| Issuer | Filings selected | Forms | Primary bodies extracted | Truncated / excluded | Full-body extraction rate | SEC requests |
|---|---:|---|---:|---:|---:|---:|
| NVIDIA (NVDA) | 5 | 4 × 8-K, 1 × 10-Q | 4 | 1 | 80.0% | 6 |
| Apple (AAPL) | 5 | 2 × 8-K, 2 × 10-Q, 1 × 10-K | 4 | 1 | 80.0% | 6 |
| Alphabet (GOOGL) | 5 | 3 × 8-K, 2 × 10-Q | 3 | 2 | 60.0% | 6 |
| **Total** | **15** | **9 × 8-K, 5 × 10-Q, 1 × 10-K** | **11** | **4** | **73.3%** | **18** |

| Form | Selected | Primary bodies extracted | Truncated |
|---|---:|---:|---:|
| 8-K | 9 | 9 | 0 |
| 10-Q | 5 | 2 | 3 |
| 10-K | 1 | 0 | 1 |

The **nine 8-K primary documents** were all marked `extracted`. This does **not** imply complete 8-K economic disclosure coverage: material exhibits (e.g. separately filed press releases) are not fetched by the current primary-document-only code.

### Confirmed exclusions visible in AAPL / GOOGL filing manifests

| Issuer | Filing date | Form | Primary-document retrieval status | Observed reason |
|---|---|---|---|---|
| AAPL | 2026-11-03 | 10-K | `truncated` | 1,500,000 downloaded bytes; HTTP response capped |
| GOOGL | 2026-10-29 | 10-Q | `truncated` | 1,500,000 downloaded bytes; HTTP response capped |
| GOOGL | 2026-07-23 | 10-Q | `truncated` | 1,500,000 downloaded bytes; HTTP response capped |

The NVIDIA 10-Q was also recorded as `truncated` in the collection audit; its individual `sec_filings.csv` manifest was not part of this report's supporting material. The four AAPL completed primary documents span **3,944–96,691 characters**, and the three GOOGL completed documents **7,475–9,310 characters**. NVIDIA's four complete bodies span **3,974–9,476 characters**.

**Interpretation:** The configured **1.5 MB HTTP-body cap** is a material issue for longer 10-Q/10-K HTML filings, even when the partially extracted text is shorter than the separate 240,000-character measurement cap. A response flagged truncated must not be scored as a complete disclosure. Do not raise caps indiscriminately to improve apparent coverage; audit memory, document sections, attachments and reproducibility first.

## Measurement status — separate from collection success

- **NVDA:** The separately supplied `research_audit.json` confirms **four eligible complete bodies scored with the official LM dictionary** and one truncated body excluded; the descriptive TF-IDF step used four documents. This is a processing validation, **not** evidence of economic predictiveness.
- **AAPL and GOOGL:** These uploads include SEC collection audits, quality reports, and filing metadata manifests. The corresponding `research_audit.json` and `research_features.csv` files were **not supplied**, so **LM scoring and no-secondary-truncation results are not independently verified for these two issuer runs here**. Do not infer that every extracted body received a valid LM polarity result.
- The GitHub Actions test suite checks offline code paths; it does not make real SEC HTTP requests and does not supply independent empirical evidence.

## Restrictions and next steps

1. Obtain AAPL and GOOGL `research_audit.json` and, preferably, `research_features.csv` from those exact runs. Verify eligible record counts, missing polarity, observed truncation flags and measurement source hashes.
2. Prioritize **8-K primary documents** for the first historical extension, but review 8-K **exhibit coverage and substance** before claiming coverage of announcements.
3. If deeper 10-Q/10-K analysis is warranted, implement **audited section-aware acquisition/extraction** rather than treating capped partial primary HTML as a whole document.
4. Distinguish `filingDate`, `acceptanceDateTime`, independently verified **first public availability**, and the pre-specified next eligible **trading session**. Current acceptance fields do not certify event-time identification.
5. Expand historical coverage only after documenting eligible yields, missingness by form and the terms of access. Neither sentiment-label validity nor stock-market forecasting is established by these 15 filings.

**Bottom line:** The **live SEC collection and primary-body extraction paths are verified at small scale for NVDA, AAPL and GOOGL** based on submitted local run audits. The current research sample is too small, form-mixed and temporally unverified to support an asset-pricing claim or a Princeton-style standalone empirical paper.
