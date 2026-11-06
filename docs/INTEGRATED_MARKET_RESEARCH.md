# Integrating Company News, SEC Disclosures and QQQ Market Outcomes

**Purpose:** A unified, auditable exploratory research step. Use the quality-controlled
LM measures from issuer/publisher news and SEC disclosures, then test their *historical association*
with stock returns relative to QQQ. **It does not generate actionable buy/sell recommendations,
calibrated directional probabilities, or causal effect estimates.**

## What links the two existing workflows?

1. **News acquisition** (dashboard, Workflow A) produces `Results/<TICKER>/Runs/<NEWS_RUN>/04_articles.csv`. These are full article bodies with source metadata.
2. **SEC collection** (Workflow B) produces `Results/<TICKER>/Research/<SEC_RUN>/corpus_local.csv` *if* eligible filing text was available. It includes SEC document dates, CIK-backed issuer identity, text status and truncation flags. The SEC quality reports are audits; they do **not** constitute positive/negative trading signals.
3. **Same-ticker text measurement** merges both corpora through the existing `research measure` command, verifying identity, removing duplicates, excluding incomplete text and rescoring on the same official LM dictionary.
4. **Market alignment** (new `research market`) reads the merged `research_features.csv` and the **previously imported Nasdaq stock/QQQ CSV pair**. It preserves news versus SEC form categories, discards incomplete/invalid LM records, aligns document dates conservatively and calculates subsequent stock-minus-QQQ returns for 1, 3 and 5 trading sessions.

## Step-by-step example (NVIDIA)

From the repository root, activate your local Python environment, install requirements, and put the official LM dictionary into
`inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`.

**First**, complete Workflow A once (English dashboard `python -m news2market --web --port 8766`). Import the actual Nasdaq `NVDA` and `QQQ` historical CSVs using the dashboard's import control, and run the news collection. Confirm its `04_articles.csv` exists and contains qualifying real article bodies.

**Second**, complete Workflow B once using a real SEC User-Agent, `--fetch-bodies`, and the same ticker. Confirm the SEC run's `corpus_local.csv` exists and includes real documents.

**Third**, join and remeasure both corpora without any new network requests:

```bash
python -m news2market research measure --ticker NVDA \
  --input-csv Results/NVDA/Runs/NEWS_RUN_ID/04_articles.csv \
  --input-csv Results/NVDA/Research/SEC_RUN_ID/corpus_local.csv
```

Replace `NEWS_RUN_ID` and `SEC_RUN_ID` with your actual run folder names. This produces another `Results/NVDA/Research/<MERGED_RUN_ID>/research_features.csv` plus `identity_audit.json` and `research_audit.json`.

**Fourth**, using the newly generated *merged* features and previously imported Nasdaq CSV pair, run:

```bash
python -m news2market research market --ticker NVDA \
  --features-csv Results/NVDA/Research/MERGED_RUN_ID/research_features.csv
```

The new output folder `Results/NVDA/Research/<MARKET_RUN_ID>/` contains:

- `market_event_alignment.csv` — each retained SEC/news document, source/form, LM text polarity, count of polarity hits, lexical tone, first later signal close and 1/3/5-session QQQ-relative outcomes when available
- `market_alignment_audit.json` — input counts, exclusions, source groups, distinct dates, usable forward windows, pricing provenance/hashes and limitations
- `market_alignment_report.md` — readable descriptive assessment and interpretation safeguards
- `research_audit.json` — execution status and summary

Repeat with `--ticker AAPL` or `GOOGL` when you have that issuer's own verified Nasdaq stock CSV and source corpora.

## Measurement design and non-negotiable safeguards

- **LM sentiment is not investor trading sentiment.** It is relative positive/negative dictionary-word usage. `positive_tone_not_buy_signal`, `negative_tone_not_sell_signal`, `balanced_lexicon_tone`, and `insufficient_lexicon_evidence` are *descriptive lexical categories*. The default **three polarity-hit threshold** is an *illustrative, unvalidated diagnostic*, not a statistically optimized buy/sell classifier. Never claim it improves returns without sufficient held-out evidence.
- **Quality gating comes first:** no scoring for metadata-only, truncated, invalid identity, or incomplete bodies. Requiring the original LM result's `eligible_for_text_measurement=True`, `text_quality=complete_body`, and no secondary truncation prevents a data quality report from being mistaken for a sentiment feature.
- **Keep document types separate:** a full 10-Q is not directly comparable to a short 8-K template or a publisher article. In the November 6 small pilot, several eligible 8-K primary documents had only one positive and one negative LM hit, which cannot justify directional trading claims.
- **Time convention:** first market *close strictly later* than the document's calendar date is treated as a *hypothetical* signal time, then subsequent session-close returns are measured. The true **first public availability time is not validated**, and no research event identification is claimed. SEC notes that acceptance and first public availability are distinct ([SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)).
- **Outcome** for horizon `h` sessions is `(P_stock,t+h/P_stock,t − 1) − (P_QQQ,t+h/P_QQQ,t − 1)`. The Nasdaq inputs are **Close/Last**, not fully dividend-adjusted total returns. QQQ is a useful Nasdaq-100 growth-stock benchmark, **but owns NVDA/AAPL/GOOGL itself**; subtracting it does not prove stock-specific alpha.
- **Statistical independence:** multiple articles on the same day and overlapping multi-day returns are correlated. The new command deliberately reports **event-level descriptive alignments**, not p-values or a strategy's performance. It will honestly report `no_later_market_outcome` when historical price CSVs end before an event's forward horizon.

## When is a real Buy/Sell study justified?

Only after a larger historical corpus with verified market-availability dates, substantive filing exhibits, independently defined labels, pre-registered trading rules, transaction costs and time-ordered *out-of-sample* testing. Useful primary evaluation outcomes would include the direction and magnitude of 1/3/5-session excess returns, uncertainty intervals, coverage, stability by filing type, and comparison with a **no-text baseline**. A small, selected 15-filing SEC pilot cannot support a profitable trading strategy claim.

## Incremental LM signal validation (experimental)

The same `research market` command now also attempts a **time-ordered, source-aware holdout experiment** after the descriptive alignment. It adds:

- `market_signal_validation.json`: audit, independent day count, chronological training/holdout diagnostics, text model and no-text baseline scores, and limitations.
- `market_holdout_predictions.csv`: one row per distinct held-out signal day, with actual 1-session stock-minus-QQQ return, both forecasts, and source-specific LM features. It is header-only when validation is unsupported.

**Unit of analysis:** one distinct eligible signal close, NOT one article. News and SEC polarity averages are retained as *separate* predictors, with source-present indicators so that an absent source is never silently interpreted as neutral. Same-day repeated documents therefore cannot multiply the return label. The lexical-insufficiency gate removes low-hit documents from directional forecasting inputs without deleting the descriptive audit.

**Fixed provisional evaluation design:** at least 40 unique informative signal days, with at least 25 training and 10 later holdout days; chronological 70/30 split; any training target at or beyond the first holdout signal date is purged. Ridge(alpha=10), with News mean polarity, SEC mean polarity and two source-presence indicators, is fit only on earlier days. The historical *training-event-day* mean of next-session excess return is the no-text baseline. Compare held-out RMSE, MAE, and directional accuracy over nonzero-return dates. There is deliberately no optimization of thresholds or trading simulation. The 40-day threshold is an **engineering minimum**, not evidence of sufficient statistical power.

**Result states:** `insufficient_evidence` (no validation conclusion, predictions header-only) or `held_out_experiment_not_trading_signal` (exploratory held-out scores, not proof of alpha). A lower RMSE versus the simple baseline is an initial incremental-information diagnostic only; it is **not** a statistically significant finding, a causal estimate, or financial advice.

**Scope limitations:** A single chronological holdout is unstable; same-day aggregation does not remove adjacent-day dependence; date-only availability and SEC exhibits remain open; training and testing only on event-days creates conditional selection; QQQ contains the target issuers; Nasdaq Close/Last excludes dividend adjustments; and LM sentiment is not a measured market surprise. Future research should add a multi-period walk-forward benchmark using all market days, verified publication timestamps, and richer non-text baselines before any Buy/Hold/Sell claims.

**Run with real data:** no extra command is required beyond the two commands already shown above. Do not confuse a passing synthetic CI test with successful local execution on genuine news, SEC, and Nasdaq files.
