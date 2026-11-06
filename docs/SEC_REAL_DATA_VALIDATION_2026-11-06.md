# SEC EDGAR Real-Data Collection Validation — November 6, 2026

**Scope:** Three *small, user-executed live SEC collection runs* using News2Market on a local Mac. Supplied files include collection audits and quality reports for all three issuers; the NVIDIA run included `research_audit.json`, and AAPL/GOOGL each additionally supplied `sec_filings.csv`, `research_audit.json`, and `research_features.csv`. The two newly supplied firm-level research CSVs were cross-checked row by row against the run audits. This document records **observed collection and text-scoring integrity, not a market return study or an independently repeated live benchmark**.

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

## LM scoring status — verified at the artifact level

| Issuer | Extracted complete bodies | Eligible SEC bodies scored by LM | Excluded truncated bodies | Among scored: missing LM polarity | LM secondary truncations in available feature CSV |
|---|---:|---:|---:|---:|---|
| NVDA | 4 | 4 | 1 | 0 | Not independently checked row by row (NVDA research audit only) |
| AAPL | 4 | 4 | 1 | 0 | **0 / 4** |
| GOOGL | 3 | 3 | 2 | 0 | **0 / 3** |
| **Total** | **11** | **11** | **4** | **0** | **0 / 7 checked at row level** |

- The three `research_audit.json` files report the *same official LM dictionary SHA256*, `e2d1328682bab7d2187684fb9f5420bb730401c9eefc00daf835edd203f4859d`, and an LM body cap of **240,000 characters**.
- AAPL: all four eligible records contain nonempty LM token counts and polarity values, with `lm_text_truncated=False`; the 10-K marked `truncated` has **no LM score**. TF-IDF used four documents, with a maximum configured vocabulary of 2,500.
- GOOGL: all three eligible 8-K records contain nonempty LM token counts and polarity values, with `lm_text_truncated=False`; the two truncated 10-Qs have **no LM scores**. TF-IDF used three documents, with 641 reported terms.
- NVDA: the supplied research audit confirms four eligible scored documents and one excluded truncated document. Its row-level `research_features.csv` was not supplied, so a claim of *row-by-row independently checked* no-secondary-truncation for NVDA would exceed the evidence. 
- The published counts are based on the user's machine-generated, real-SEC-run audit artifacts, and do not constitute independent re-extraction of the live source pages.

### Measurement-validity caution from the newly verified feature rows

In the supplied **AAPL 8-K primary-document** rows, both positive and negative LM word counts were **1 and 1** (polarity `0.0`). All three **GOOGL 8-K primary-document** rows also had **1 positive and 1 negative hit** (polarity `0.0`). This pattern could reflect repeated filing templates or a lack of substantive economic text in the selected *primary* document. **Do not interpret a zero lexicon polarity as an economically neutral event or a null market reaction.** Item-level exhibits and press releases were not yet fetched or semantically inspected.

AAPL's two eligible 10-Qs have substantially more text and negative LM polarities of approximately **-0.742424** and **-0.794286**. These are **dictionary values, not measures of abnormal returns or verified financial news shocks**. A direct 8-K versus 10-Q comparison without controlling for source length, boilerplate, form and content would be invalid.

The observed result validates **collection, integrity screening and deterministic LM scoring** for a small selected sample. It does **not** establish that LM represents firm fundamentals, economic surprises, trading signals, or predictive power.

## Restrictions and next steps

1. **Completed:** AAPL/GOOGL `research_audit.json` and `research_features.csv` were received and cross-checked. For a more extensive independently reproduced audit, retain full raw filing text and run-level checksums locally under applicable source terms.
2. Prioritize **8-K primary documents** for the first historical extension, but review 8-K **exhibit coverage and substance** before claiming coverage of announcements.
3. If deeper 10-Q/10-K analysis is warranted, implement **audited section-aware acquisition/extraction** rather than treating capped partial primary HTML as a whole document.
4. Distinguish `filingDate`, `acceptanceDateTime`, independently verified **first public availability**, and the pre-specified next eligible **trading session**. Current acceptance fields do not certify event-time identification.
5. Expand historical coverage only after documenting eligible yields, missingness by form and the terms of access. Neither sentiment-label validity nor stock-market forecasting is established by these 15 filings.

**Bottom line:** Small-sample **live SEC collection and LM research scoring are verified across all three issuers** using the supplied audits, with AAPL/GOOGL also checked at the feature-row level. This **completes the engineering pilot's three-company real-data validation milestone**. However, the 15 selected disclosures are too few, form-mixed, mostly short 8-K primary files, and temporally unverified to support an asset-pricing inference, a validated sentiment classifier, or a Princeton-style empirical research paper.
