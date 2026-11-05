# News2Market — Exploratory Research Report

**Historical pilot date:** November 5, 2026.  
**Research status:** A small observational finance-text and data-engineering prototype. Current software supports three selectable companies; the numerical findings below are for **NVIDIA only**.

## Research question and evidence

Can first-party financial announcements and independent editorial articles be transformed into auditable textual measurements, and do those measurements show any simple relationship with later stock returns? The engineering workflow collects URLs, timestamps where available, source types, full text, dictionary measurements and market outcomes. Textual tone is not itself an identified causal economic surprise.

### NVIDIA first-party issuer-news pilot

* **Issuer text:** 30 real NVIDIA Newsroom announcements in the configured 2026-08-01 through 2026-11-04 study window; **29** with at least one positive or negative LM dictionary match.
* **Price source:** user-provided official Nasdaq `NVDA.csv` and `QQQ.csv`, **1,254** matched trading sessions from **2021-11-05 to 2026-11-04**. The raw `Close/Last` field is not cash-dividend adjusted.
* **Measurement:** `LM polarity = (P−N)/(P+N)` when `P+N>0`; missing otherwise. Original text and a separately cleaned version help audit source-specific boilerplate.
* **Conservative alignment:** With only day-level publication timestamps, news is mapped to a later market close before using the following close-to-close return difference. It is not a causal timing identification strategy.

| Quantity | Observed |
|---|---:|
| News items | 30 |
| Items with LM polarity hits | 29 |
| Dated signal sessions in regression | 18 |
| Pearson correlation | −0.0353 |
| OLS LM polarity slope | −0.001736 |
| HC1 heteroskedasticity-robust SE | 0.009859 |
| Exploratory p-value | 0.8602 |
| R² | 0.001246 |

![Exploratory NVIDIA issuer-news regression scatterplot](figures/09_signal_vs_return.png)

**Interpretation:** This very small regression does not demonstrate a simple linear association or profitable predictive signal. HC1 errors are not autocorrelation-robust; stock-minus-QQQ price returns are not factor-adjusted abnormal returns. The result cannot be generalized to AAPL/GOOGL or all U.S. stocks.

### Independent third-party RSS trial

On November 5, 2026, the original external RSS test attempted eight public feeds, of which six returned usable feed data; it deduplicated and extracted **two** qualifying full publisher texts. Both had LM polarity hits: TechCrunch on Box/NVIDIA Nemotron scored **+0.142857** and CNBC on Moonshot/NVIDIA Blackwell scored **+0.500000** (unchanged by that trial's narrative-cleaning operation). Both have day-level publication dates without independently verified first-market-availability timestamps. These values **were not joined** into the issuer-news return regression.

### Resource-constrained local LLM audit

Ollama with `qwen2.5:1.5b` was tested on the 30 issuer articles using constrained JSON outputs, source-text excerpts and evidence IDs. **9/30** outputs passed structural/evidence checks, **3/30** required manual review and **18/30** failed. A common failure was scores outside the permitted range (e.g. 4 instead of [-1,1]); channel categories sometimes collapsed to `Investor_Relations`. These failures were preserved, not silently clipped. Exact quotation matching is not independent validation of economic meaning. The ten AI-assisted reference labels are **not** blinded human ground truth.

## Research implications and next steps

1. Dictionary frequencies and polarity are transparent but can be misleading when only a few sentiment words match or when legal boilerplate dominates the language.
2. Company announcements and independent reporting must be distinguished; a positive announcement may already be priced or disappoint prior expectations.
3. Reliable future market-response research needs more company-balanced and date-stamped news, authorized higher-quality price data, better intraday release timestamps, robust risk adjustment and human-validated measurement.
4. The current single-codepath three-company interface is an **engineering generalization**, not verified comparative empirical results for all three firms.

This project was developed independently on a memory-constrained personal Mac without paid data or LLM APIs. More permitted data, compute and labeling resources could support future extension, **but no improvement is claimed before empirical testing**.
