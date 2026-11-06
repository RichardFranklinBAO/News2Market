# News2Market

**An auditable Financial NLP & Empirical Research Pipeline.**

News2Market integrates U.S. company news (Workflow A), SEC EDGAR disclosures (Workflow B), Loughran–McDonald (LM) financial text measures, and subsequent stock-versus-QQQ returns in one Python workflow.

**Status: Phase I engineering prototype completed (November 2026).** The pipeline has been run on real NVDA, TSLA and AMD data. It does **not** establish predictive power, abnormal returns, causality or a profitable trading strategy.

## What is implemented

- **Data collection:** U.S. stock ticker/SEC CIK lookup, news discovery and full-text extraction, selected SEC 8-K/10-Q/10-K primary-document retrieval.
- **Financial NLP:** source-aware text cleaning, completeness and identity checks, LM dictionary word counts/polarity, and descriptive TF-IDF.
- **Empirical alignment:** matched stock/QQQ daily prices, 1/3/5-session relative price returns, and source-specific News/SEC features.
- **Research safeguards:** exclusion and provenance audits, same-day event aggregation, and a conditional chronological holdout that returns `insufficient_evidence` when samples are inadequate.

### NLP research roadmap

| Layer | Research goal | Phase I status |
|---|---|---|
| **1. Lexical measurement** | Quantify finance-related language with a transparent LM dictionary | **Implemented** |
| **2. Contextual semantics** | Interpret negation, comparisons, sentence meaning and document context (e.g., FinBERT or carefully evaluated LLMs) | **Future work** |
| **3. Economic information & expectations** | Separate absolute sentiment from **surprises relative to prior market expectations**, using expectations and realized outcomes | **Future work** |

An earlier optional local LLM-labeling experiment is not a validated implementation of Layers 2–3.

## Observed results

User-executed local unified runs, **November 6, 2026**:

| Stock | Eligible news bodies | SEC filings selected | Market-aligned events | Informative distinct days |
|---|---:|---:|---:|---:|
| NVDA | 8 | 4 | 11 | 5 |
| TSLA | 0 | 4 | 3 | 1 |
| AMD | 0 | 5 | 3 | 2 |

All three completed the engineering workflow, but each returned **`insufficient_evidence`** for holdout validation. Only the NVDA run contained both eligible News and SEC texts; TSLA and AMD yielded SEC-only aligned events. **A+B are integrated in software, not yet proven complementary in an empirical model.** Counts refer to separate runs, not a pooled research sample.

A separate historical NVDA issuer-news pilot (18 signal sessions) found no simple linear return association (*r* = −0.0353; exploratory HC1 *p* ≈ 0.8602). See the **[Phase I Research Note](docs/RESEARCH_NOTE_PHASE_I.md)** for scope, methods, and evidence.

## Quick start

Python 3.11–3.12 recommended. Install dependencies and the [official LM dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) at `inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`. SEC access requires a genuine contact User-Agent.

```bash
python -m pip install -r requirements.txt
export N2M_SEC_USER_AGENT="Your Real Name your-email@example.com"
python run_all.py                  # Interactive U.S. stock selection
# Alternatively: python run_all.py --ticker AMD
```

**No market-price API key needed.** Price retrieval tries a verified Yahoo cache, unofficial keyless `yfinance`, then a previously registered Nasdaq stock/QQQ CSV pair. If both fail, the Terminal prints relevant Nasdaq download links and setup steps.

For genuine Nasdaq historical exports, rename and place files in `inputs/prices/AMD.csv` and `inputs/prices/QQQ.csv` (replace AMD with your ticker), then register their user-attested source and hashes:

```bash
python run_all.py --ticker AMD --prices nasdaq --confirm-nasdaq
```

Files must contain `Date` and `Close/Last`. An alternative import directly from Downloads is documented in the [one-command setup guide](docs/ONE_COMMAND_WORKFLOW.md). Run results and audits are stored under `Results/<TICKER>/Unified/<RUN_ID>/`.

## Limitations & future directions

1. **Incomplete historical text coverage.** RSS timeouts, publisher restrictions and limited archives yield sparse and nonrandom news coverage (zero eligible news bodies for TSLA/AMD). **Next:** authorized historical archives, improved multi-firm retrieval, coverage and missingness audits.
2. **Incomplete SEC event content.** Only selected recent primary filings are collected; some long documents are truncated and **8-K exhibits are not systematically retrieved**. **Next:** section-aware extraction and exhibit capture with quality controls.
3. **Lexicon is not semantic understanding.** LM scores count dictionary terms but may misinterpret negation, comparisons and context (e.g., “losses narrowed”). **Next — NLP Layer 2:** validate contextual models such as FinBERT or LLM-based event interpretation against independently checked labels. No semantic accuracy is claimed yet.
4. **Sentiment is not economic surprise.** Even an accurate positive/negative interpretation cannot establish whether results exceed **prior investor or analyst expectations**. **Next — NLP Layer 3:** link disclosures to prior guidance/forecasts, realized fundamentals and market expectations; distinguish anticipated information from unexpected news.
5. **Timing, benchmark and statistical limits.** Public availability timestamps remain unverified; date-based alignment is **not a causal event study**. Stock-minus-QQQ returns are not factor-adjusted alpha, and raw Nasdaq `Close/Last` differs from Yahoo adjusted prices. With only 5/1/2 informative days, the provisional 40-day engineering minimum is unmet; **no out-of-sample prediction model was fitted**. **Next:** larger independent samples, pre-specified hypotheses, source ablations (News-only, SEC-only, combined), adjusted risk benchmarks and walk-forward evaluation.
6. **Operational reliability and data rights.** The default keyless Yahoo feed can rate-limit; manual Nasdaq downloads may be needed. **Next:** consider *optional* personal API-key providers subject to licensing/provenance review. Third-party prices, news bodies and the LM dictionary are not redistributed.

**Documentation:** [Research Note](docs/RESEARCH_NOTE_PHASE_I.md) · [Setup](docs/ONE_COMMAND_WORKFLOW.md) · [Market methodology](docs/INTEGRATED_MARKET_RESEARCH.md) · [NVDA pilot](docs/RESEARCH_REPORT.md) · [SEC audit](docs/SEC_REAL_DATA_VALIDATION_2026-11-06.md)

*Independent exploratory research prototype. Not investment advice. No software reuse license is currently granted.*
