# News2Market

**Financial NLP · Alternative Data · Empirical Research**

## 1. Project Overview

News2Market is an independent, reproducible Python research prototype exploring a question in empirical finance: **Can public company news and SEC disclosures be transformed into reliable textual measures and related to subsequent stock-market outcomes?**

It integrates **company news (Workflow A)** and **SEC EDGAR filings (Workflow B)**, applies the Loughran–McDonald (LM) financial dictionary, and aligns measured text with **1-, 3-, and 5-trading-session stock returns relative to QQQ**. News and SEC remain distinguishable sources; identity, text quality, data provenance and exclusions are audited rather than silently discarded.

**Phase I (November 2026): implemented and exercised on real NVDA, TSLA and AMD data.** This is an exploratory research pipeline, **not** a demonstrated return-prediction or trading system.

**Code organization:** Stage-specific helper scripts are grouped under [scripts/](scripts/) (collection, preparation, NLP, market data, and reporting); the user-facing entrypoint remains `run_all.py`.

**Run locally** (Python 3.11–3.12; [setup details](docs/ONE_COMMAND_WORKFLOW.md)):

```bash
python -m pip install -r requirements.txt
# Install the official LM dictionary in inputs/ (see linked setup guide).
export N2M_SEC_USER_AGENT="Your Real Name your-email@example.com"
python run_all.py                       # Choose a U.S. stock ticker in Terminal
# Or: python run_all.py --ticker AMD
```

Market prices use a **keyless Yahoo/cache path** with a user-verified Nasdaq CSV fallback. If automatic access fails, the program displays ticker-specific download links and file instructions. Complete outputs and audits are saved under `Results/<TICKER>/Unified/<RUN_ID>/`.

## 2. Research and Technical Skills Demonstrated

| Skill | Evidence in this project |
|---|---|
| **Web scraping and alternative-data collection** | Automated company-news discovery and article extraction; official SEC EDGAR filing retrieval; ticker/CIK and source verification. |
| **Research dataset construction** | Parsing, deduplication, source labeling, missingness/completeness checks, document hashes, and joining News/SEC features to stock–QQQ market outcomes. |
| **Python NLP and text measurement** | LM financial-word counts and sentiment polarity, descriptive TF-IDF, source-specific text features, and safeguards against low-information or truncated documents. |
| **Statistical and computational analysis** | Event-date/return alignment, 1/3/5-session relative-return calculations, daily aggregation to reduce pseudo-replication, and a separate exploratory NVDA OLS analysis with HC1 standard errors. |
| **Research design and communication** | An implemented chronological Ridge-versus-no-text validation **protocol** (not fitted on the insufficient live samples), transparent negative results, auditable reports, and an English [Research Note](docs/RESEARCH_NOTE_PHASE_I.md). |

These are demonstrated components of this project—not claims to have implemented OCR, randomized experiments, structural economic models, or a fully trained predictive ML system.

## 3. Project Results

**Observed local end-to-end runs — November 6, 2026**

| Stock | Eligible news full texts | SEC filings selected | Market-aligned events | Informative independent signal days |
|---|---:|---:|---:|---:|
| NVDA | 8 | 4 | 11 | 5 |
| TSLA | 0 | 4 | 3 | 1 |
| AMD | 0 | 5 | 3 | 2 |

- **Engineering milestone:** All three companies completed the collection/measurement/market-alignment pipeline. AMD was aligned against **1,253** matching stock–QQQ trading sessions.
- **Actual A+B integration:** NVDA yielded both eligible News and SEC observations; the TSLA and AMD aligned samples were **SEC-only** because no qualified news full texts were found.
- **Statistical result:** Every unified run reported `insufficient_evidence`; **no out-of-sample forecasting model was fitted** and no predictive advantage was established.
- **Separate earlier NVDA pilot:** 18 dated issuer-news signal sessions; LM polarity versus next-session QQQ-relative return had Pearson *r* = −0.0353 and exploratory HC1 *p* ≈ 0.8602 (**no evidence of a simple linear association**). This is a different sample and is not pooled with the unified runs.

The [Phase I Research Note](docs/RESEARCH_NOTE_PHASE_I.md) documents methods, interpretation and source limitations. Detailed [SEC collection audits](docs/SEC_REAL_DATA_VALIDATION_2026-11-06.md) and [market-alignment methodology](docs/INTEGRATED_MARKET_RESEARCH.md) are also available.

## 4. Limitations and Future Directions

1. **News coverage and representativeness.** RSS timeouts, inaccessible articles and incomplete historical archives produced **zero qualified news bodies for TSLA/AMD**; multiple years of price data cannot repair sparse text data. *Next:* authorized historical news sources, broader issuer coverage and explicit missingness/selection analysis.
2. **Incomplete SEC disclosures.** Only selected recent primary 8-K/10-Q/10-K documents are retrieved; lengthy filings can be truncated and **8-K exhibits are not comprehensively included**. *Next:* verified exhibit collection and section-aware extraction.
3. **NLP Layer 1 — lexical measurement, not contextual understanding.** LM word balance may miss negation, comparisons and domain-specific meaning (e.g., “losses narrowed”). *Next, Layer 2:* evaluate contextual models such as FinBERT or constrained LLM-based information extraction against independently checked labels; **this semantic capability has not been validated**.
4. **NLP Layer 3 — economic surprise and expectations.** Even correctly identifying positive language does not show whether disclosed information was **better or worse than prior market expectations**. *Next:* link text to analyst forecasts, prior management guidance, realized fundamentals and measures of unexpected information. This economic-expectations layer is **not yet implemented**.
5. **Market timing and inference.** Document calendar dates do not verify first public availability; stock-minus-QQQ price returns are **not causal effects or factor-adjusted alpha**, and QQQ contains the firms studied. Nasdaq raw `Close/Last` and Yahoo adjusted closes have different price bases. The observed 5/1/2 informative dates are below the provisional **40-day engineering gate**, which itself is not proof of statistical power. *Next:* verified timestamps, larger independent samples, News-only/SEC-only/combined ablations, stronger risk-adjusted benchmarks and walk-forward evaluation.
6. **Price access and reproducibility.** Unofficial keyless Yahoo data may be rate-limited; the manual Nasdaq fallback requires genuine user-attributed CSVs. *Next:* consider an **optional personal API key** provider after reviewing coverage, licensing and provenance. Third-party article text, market prices and the LM dictionary are not redistributed.

**Research status:** Phase I demonstrates financial-data engineering, NLP measurement and reproducible exploratory analysis. **Validated economic mechanisms, incremental predictive value and a profitable trading strategy remain open research questions.**

*Independent exploratory research prototype; not investment advice. No software reuse license is currently granted.*
