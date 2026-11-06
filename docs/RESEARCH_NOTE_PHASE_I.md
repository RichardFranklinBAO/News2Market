# News2Market — Phase I Research Note

**Financial NLP, Disclosure Measurement, and Exploratory Market Alignment**  
**Independent research/engineering prototype | November 6, 2026**  
**Status:** Implemented and exercised on live public data; **not** a validated predictive or causal finance study.

## Abstract

This note documents News2Market, a reproducible Python pipeline linking company-related news and SEC EDGAR primary disclosures to transparent Loughran–McDonald (LM) financial-text features and subsequent U.S. stock returns relative to QQQ. A single command performs issuer verification, data collection, quality screening, LM measurement, date-based market alignment, and a conditional out-of-sample diagnostic. The engineering contribution is **source-aware integration with explicit failure and missingness audits**, not a new financial NLP estimator. In November 2026, local end-to-end runs completed for NVIDIA (NVDA), Tesla (TSLA), and Advanced Micro Devices (AMD). Their respective counts of eligible news full texts were **8, 0, 0**; market-aligned events were **11, 3, 3**; and informative independent signal dates were only **5, 1, 2**. All three runs correctly returned `insufficient_evidence` instead of model-performance claims. A separate earlier NVIDIA issuer-news pilot (18 dated signal sessions) found no measurable simple linear association with next-session relative returns (Pearson *r* = −0.0353; exploratory HC1 *p* ≈ 0.8602). These results establish a functional, auditable financial-text workflow while demonstrating why larger, better-timed text samples are needed for economic inference.

## 1. Research question and economic motivation

**Can disclosures and reported company news be converted into transparent, auditable measures of financial text, and do those measures contain information about subsequent returns beyond simple benchmarks?**

The motivating empirical distinction is between **observable language** and **unexpected economic information**. The same financial words may reflect boilerplate, prior market expectations, strategic issuer communication, or genuinely new information. Accordingly, a dictionary score is treated as a *lexical measurement*, not as an identified investor belief, exogenous shock, or trading recommendation.

## 2. Implemented design

**Two input streams, one measurement framework.** Workflow A discovers issuer/publisher news, extracts eligible full text, deduplicates candidate items, and records source URLs and document-date metadata. Workflow B identifies the target company by SEC CIK and retrieves selected recent 8-K/10-Q/10-K primary documents from SEC EDGAR. Complete, source-identified documents are remeasured with the same official LM dictionary; incomplete or truncated bodies are excluded from full-text inference. News and SEC retain distinct feature-group labels, rather than being pooled as interchangeable documents.

For text *i*, a descriptive polarity is

\[
S_i = \frac{P_i-N_i}{P_i+N_i},\quad P_i+N_i>0,
\]

where *P* and *N* are matched LM positive and negative word counts. Missing or very low-hit measurements are not treated as meaningful Buy/Sell labels. Descriptive TF-IDF is supplementary.

**Market alignment.** For each eligible document, the first trading-session **close strictly after the document's calendar date** is the hypothetical signal close. For horizons *h* = 1, 3, 5 trading sessions,

\[
Y_{i,h}=\left(\frac{P^{stock}_{t+h}}{P^{stock}_{t}}-1\right)
-\left(\frac{P^{QQQ}_{t+h}}{P^{QQQ}_{t}}-1\right).
\]

The outcome is a simple stock-minus-QQQ *price-return difference*, **not** a factor-adjusted abnormal return. The user-confirmed Nasdaq `Close/Last` fallback is unadjusted for cash dividends; the alternative Yahoo series is adjusted, and the pipeline logs the source/basis so they are not silently mixed.

**Exploratory incremental-information gate.** Repeated same-session events are aggregated to one dependent return observation. A fixed Ridge model (four features: daily mean News LM polarity, mean SEC LM polarity, and two source-presence indicators) is designed for chronological holdout comparison with a no-text training-period mean-return baseline. The software requires **at least 40 distinct informative signal days**, including at least 25 training and 10 holdout days, and purges an overlapping label at the boundary. This is a provisional *engineering minimum*, not a sufficient-power calculation. When the threshold or quality checks fail, the model is not fitted and held-out predictions are not invented.

## 3. Observed Phase I evidence

### 3.1 End-to-end live company runs

| Issuer | Eligible news full texts | SEC filings selected | Text events aligned to market | Informative distinct signal days | Holdout status |
|---|---:|---:|---:|---:|---|
| NVDA | 8 | 4 | 11 | 5 | Insufficient evidence |
| TSLA | 0 | 4 | 3 | 1 | Insufficient evidence |
| AMD | 0 | 5 | 3 | 2 | Insufficient evidence |

**Interpretation.** All three user-executed local workflows reached the market-alignment output. The AMD run used **1,253 matched stock/QQQ price sessions**, confirming the price-join path for a newly selected ticker. These are small, separate case studies. Only NVDA actually supplied both news and SEC texts in the corresponding unified run; TSLA and AMD yielded **SEC-only aligned event sets** because no eligible news full texts were collected. Thus the architecture integrates A+B, but **incremental information from combining A+B was not empirically established**. Counts describe the Terminal run summaries, not an independently replicated raw-source audit.

### 3.2 Separate, earlier exploratory checks

An earlier NVIDIA issuer-news pilot comprised 30 Newsroom announcements, 29 with positive/negative LM dictionary hits, and **18 dated signal sessions** in a simple descriptive regression. Its observed Pearson correlation between LM polarity and subsequent QQQ-relative return was **−0.0353**, with slope **−0.001736**, HC1-robust exploratory *p* ≈ **0.8602**, and *R²* ≈ **0.00125**. This is **not** a significant or generalizable association. The pilot is methodologically distinct from the unified 8-news/4-SEC local run; the samples and counts must **not** be combined into one inference.

A separate SEC collection-quality pilot selected **15 filings** across NVDA, AAPL, and GOOGL: **11 complete primary-document bodies** were eligible for LM scoring and **4 truncated documents** were excluded. Its selected primary 8-K documents were retrieved, but important **8-K exhibits** were not comprehensively fetched. This audit concerns retrieval/measurement integrity, **not** stock-return predictability.

## 4. Limitations and interpretation boundaries

1. **Selection, coverage, and scale.** Recent RSS feeds do not provide reliable historical backfills; Google News timeout and narrow third-party coverage produced zero eligible articles for TSLA and AMD. SEC sampling relies on recent submissions. Company, source and time-window selection is nonrandom, and 5/1/2 informative dates are vastly below a credible inferential dataset. Five years of prices cannot replace missing historical text.
2. **Disclosure completeness.** Long 10-Q/10-K primary documents can exceed configured retrieval or measurement caps; incomplete bodies are deliberately excluded. Separate 8-K exhibits and substantive attached press releases may be omitted. A successfully downloaded filing is not necessarily complete economic event coverage.
3. **Construct validity.** LM counts can be driven by document length, legal language and template boilerplate. A positive/negative word balance is **not** validated belief formation, surprise relative to expectations, or economic news direction. No independent blinded human labeling establishes construct validity.
4. **Timing and identification.** Calendar document dates do not prove precise first public dissemination. The “first later close” convention is cautious but not a verified tradable entry time; filing acceptance is not automatically the first market-information timestamp. No causal event study is implemented.
5. **Market outcomes and inference.** Simple close-to-close stock-minus-QQQ differences are not risk-adjusted or total-return alpha. QQQ contains the studied firms; same-day clusters, adjacent observations and overlapping horizons can be dependent. No completed holdout model, strategy, confidence interval for alpha, trading costs, or directional forecasting advantage exists.
6. **Reliability and data rights.** Unofficial keyless Yahoo downloads may be rate-limited and require manual, user-attested Nasdaq price CSV fallback. Yahoo adjusted closes differ from raw Nasdaq prices. SEC and publisher access policies and redistribution rights constrain raw-text and price-data releases. Passing synthetic offline tests validates software logic, **not** a prospective live-data performance benchmark.

## 5. Future research directions (not implemented or established)

- **Better historical measurement:** obtain licensed, date-complete issuer/publisher archives; record source-specific coverage denominators and systematic missingness; improve broad-company news discovery without weakening identity checks.
- **Complete disclosures and valid timestamps:** retrieve and audit 8-K exhibits plus relevant 10-Q/10-K sections; independently verify publication/EDGAR availability times and session alignment.
- **Economically grounded tests:** distinguish expected versus unexpected language with external expectations/announcements, validate labels with human judgments, compare adjusted-price and factor-based benchmarks, and control source/form/firm heterogeneity.
- **Credible external validation:** use larger independent event-date panels, pre-specified hypotheses, walk-forward evaluation, source-specific ablations (News-only, SEC-only, News+SEC), uncertainty reporting, realistic transaction costs, and robust no-text baselines.
- **Operational extensions:** consider opt-in authenticated price-data providers with explicit terms and provenance if the no-key data path proves unreliable.

## 6. Scope of contribution and reproducibility

**What is finished:** a runnable, multi-ticker, source-audited financial-text ETL/measurement and descriptive stock–QQQ alignment pipeline, with a conservative insufficient-evidence safeguard. **What is not finished:** a publishable independent asset-pricing test, verified news-and-SEC synergy, or profitable trading algorithm.

For the current entrypoint, install `requirements.txt`, provide the official locally installed LM dictionary and a genuine SEC User-Agent, then run `python run_all.py`. The script first attempts no-key Yahoo price retrieval/cache and uses confirmed Nasdaq CSVs if necessary. Per-run `unified_audit.json`, `price_audit.json`, `research_features.csv`, `market_event_alignment.csv`, `market_signal_validation.json` and related audits make the measurement and exclusion logic inspectable. Raw third-party data are intentionally not bundled.

**Evidence and methods:** [Unified market design](INTEGRATED_MARKET_RESEARCH.md) · [NVIDIA historical pilot](RESEARCH_REPORT.md) · [SEC real-data validation](SEC_REAL_DATA_VALIDATION_2026-11-06.md) · [One-command instructions](ONE_COMMAND_WORKFLOW.md).

*Independent research prototype. Exploratory historical analysis only; not investment advice.*
