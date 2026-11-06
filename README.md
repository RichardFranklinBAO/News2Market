# News2Market

**A reproducible financial NLP and empirical data-engineering prototype.** News2Market brings company news, SEC EDGAR disclosures, Loughran–McDonald (LM) financial text measures, and U.S. stock-vs-QQQ forward returns into one auditable Python workflow.

**Status — Phase I complete (engineering pilot, November 2026).** Live workflows ran for NVDA, TSLA and AMD; **no predictive advantage, tradable alpha or causal effect has been established**.

## What it does

- **Collect:** Verify U.S. stock ticker/SEC CIK; retrieve identifiable news bodies and SEC 8-K/10-Q/10-K primary filings.
- **Measure:** Apply the official LM dictionary; audit source identity, text completeness, truncation and missing values; retain News and SEC as separate feature groups.
- **Align and assess:** Compute 1/3/5-session stock-minus-QQQ close returns; aggregate repeated same-day events; attempt a chronological, source-aware holdout **only when sufficient data exist**.
- **Reproduce:** Keep source hashes, price basis, exclusion reasons and run-level audit files. An insufficient sample yields `insufficient_evidence`, **not** a fabricated forecast.

### Observed live runs (November 6, 2026)

| Ticker | News full texts | SEC filings selected | Market-aligned events | Informative distinct days |
|---|---:|---:|---:|---:|
| NVDA | 8 | 4 | 11 | 5 |
| TSLA | 0 | 4 | 3 | 1 |
| AMD | 0 | 5 | 3 | 2 |

These are **small, separate local runs**, not pooled independent observations. News and SEC share the pipeline, but only the NVDA run contained both sources. All three held-out assessments returned `insufficient_evidence`. See the **[Research Note](docs/RESEARCH_NOTE_PHASE_I.md)** for methods, provenance, interpretation and limitations.

## Quick start

Python **3.11–3.12** recommended. Install dependencies, download the [official LM dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) to `inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`, and set an identified SEC User-Agent:

```bash
python -m pip install -r requirements.txt
export N2M_SEC_USER_AGENT="Your Real Name your-email@example.com"
python run_all.py                 # Choose a U.S. stock ticker in Terminal
# Or: python run_all.py --ticker AMD
```

**No market-data API key required.** Prices are attempted via a verified Yahoo cache, then unofficial `yfinance`, then an already registered local Nasdaq pair. If neither works, Terminal prints Nasdaq URLs and instructions. Download genuine company and QQQ historical CSVs; save as `inputs/prices/AMD.csv` and `inputs/prices/QQQ.csv`, then register and run once:

```bash
python run_all.py --ticker AMD --prices nasdaq --confirm-nasdaq
```

This validates `Date`/`Close/Last`, records user-attested source and SHA256 in `SOURCE_MANIFEST.json`. Do not label a file as Nasdaq unless it came from Nasdaq. [Detailed setup and fallback guide](docs/ONE_COMMAND_WORKFLOW.md).

## Limitations and next steps

1. **Sparse, selected text:** RSS may time out or lack archived full articles; TSLA/AMD had zero qualified news bodies. News/SEC incremental value cannot yet be compared reliably; multi-year prices do **not** imply multi-year text coverage.
2. **Partial disclosure capture:** SEC is sampled from recent filings; some 10-Q/10-K bodies are truncated and excluded; material 8-K exhibits are not systematically collected.
3. **Measurement and timing:** LM word balance is not a validated economic surprise. Article/filing **first public availability** is unverified; date-based market alignment is not an identified event study.
4. **Outcome and inference:** Stock-minus-QQQ is not risk-adjusted alpha; QQQ holds the analyzed stocks. Raw Nasdaq `Close/Last` lacks dividend adjustment and differs from Yahoo adjusted closes. Independent informative days (5/1/2) fall below the provisional **40-day engineering gate**; no fitted out-of-sample model or trading-performance claim.
5. **Provider and research scale:** Keyless Yahoo can rate-limit; local Nasdaq exports may be needed. Future work: improve licensed historical news coverage and issuer matching, fetch SEC exhibits/sections, verify timestamps, normalize adjusted prices, and test pre-specified economic baselines with multi-period walk-forward evaluation. An **optional personal API key** provider could improve reliability later; it is **not** part of the default price workflow.

**Docs:** [Research Note](docs/RESEARCH_NOTE_PHASE_I.md) · [Full one-command guide](docs/ONE_COMMAND_WORKFLOW.md) · [Methods](docs/INTEGRATED_MARKET_RESEARCH.md) · [Historical NVDA exploratory pilot](docs/RESEARCH_REPORT.md) · [SEC audit](docs/SEC_REAL_DATA_VALIDATION_2026-11-06.md)

**Data and rights:** Market prices, publisher article bodies and the LM dictionary are not redistributed. No software reuse license is currently granted.
