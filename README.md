# News2Market

**Automated financial-news discovery and economic-text measurement | Zero paid APIs | Exploratory pilot**

> **Research status (November 5, 2026):** A reproducible engineering prototype with limited empirical validation. It is **not** a profitable trading strategy, a causal study, or a validated financial language model.

## Why this project?

Financial news text is easy to collect and score, but difficult to measure consistently. News2Market asks three practical research questions:

1. How much do issuer boilerplate and source choice affect finance-specific lexicon scores?
2. Can a small **local** language model extract economically meaningful information while passing structured-output and evidence audits?
3. Is any tentative news tone associated with later equity returns in a small, explicitly exploratory pilot?

## What it actually does

| Stage | Implementation | Key caveat |
|---|---|---|
| Official company disclosures | NVIDIA Newsroom HTML and SEC filing support | First-party press releases are not independent journalism |
| Automatic third-party discovery | Google/Bing search RSS plus publisher RSS; deduplication and fallback | One pilot found only two full-text articles; feeds may break or be blocked |
| Text extraction | Restrained HTTP, source metadata, conservative access handling | No paywall, CAPTCHA, or authorization bypass; respect robots and publisher policies |
| Dictionary tone | Official Loughran–McDonald (LM) word lists | Lexicon tone ≠ economic impact, expectations, or future returns |
| Local LLM (optional) | Ollama Qwen2.5 1.5B; evidence-ID audit | Model scores/labels remain unvalidated; errors preserved |
| Exploratory return analysis | User-provided NVDA / QQQ historical prices, daily aggregation, HC1 OLS | 18 signal days, unknown precise release time, no out-of-sample test |

## Technical implementation and engineering workflow

This is a **modular Python research pipeline**, not just a sentiment-scoring demo. The stages below describe implemented functionality and distinguish demonstrated results from unvalidated research extensions.

| Step | Implemented technique | Main implementation |
|---|---|---|
| 1. Study setup and entity resolution | YAML-controlled ticker/benchmark, news dates, SEC CIK matching or NVIDIA-specific collection, run-specific UTC IDs | `Inputs/config.yaml`, `run_all.py`, `Scripts/00_resolve_company.py` |
| 2. Issuer news acquisition | Requests/BeautifulSoup parsing of NVIDIA Newsroom announcements; optional SEC support | `Scripts/02_scrape_articles.py`, `Scripts/03_collect_filings.py` |
| 3. Automatic third-party discovery | Search and publisher RSS feeds; XML parsing, date/title relevance filtering, URL normalization, multi-source fallback and deduplication; **no manually seeded article URLs** in the automatic run | `Scripts/15_auto_external_news.py` |
| 4. Responsible body extraction | Permitted publisher HTML retrieval, `trafilatura` extraction, minimum-length/body checks, source-date audit, 429/403 handling without bypassing protections | `Scripts/03b_scrape_external.py`, `Scripts/15_auto_external_news.py` |
| 5. Text quality and cleaning | Normalized-URL/text deduplication; preserve raw evidence; identify and trim known first-party boilerplate in a separate cleaned field; compare original versus cleaned scores | `Scripts/04_clean_deduplicate.py`, `Scripts/11_prepare_text.py`, `Scripts/11b_lm_cleaned.py` |
| 6. Financial lexicon measurement | Official Loughran–McDonald positive/negative dictionary lookups; word counts, missing-value handling, and document-level polarity `(positive - negative)/(positive + negative)` | `Scripts/05_lm_sentiment.py`, `Scripts/lm_dictionary.py` |
| 7. Optional local LLM labeling | Ollama HTTP inference, Qwen2.5 1.5B, constrained JSON output, event categories, economic-channel labels and numbered excerpts; schema/range/quote audits and retry logs | `Scripts/12_local_llm_labels.py` |
| 8. Market dataset and alignment | Import user-supplied daily Nasdaq CSVs, parse dates and raw `Close/Last`, join NVDA and QQQ trading days, aggregate news scores, conservatively align outcomes after reported news dates | `Scripts/07_get_prices.py`, `Scripts/08_build_signals.py`, `Scripts/signal_core.py` |
| 9. Exploratory inference | Pearson correlation, OLS with HC1 heteroskedasticity-robust SE, coefficient/p-value/R² and diagnostic scatterplot; no causal or backtest claims | `Scripts/09_validate.py` |
| 10. Audit and reproducibility | Per-run CSV/JSON provenance, original input hashes, raw-versus-cleaned measurement, model-failure preservation, isolated external runs, offline unit tests and documentation | `Results/<TICKER>/<UTC_run_id>/`, `tests/`, `docs/` |

**Software stack:** Python 3.11–3.12; `requests`, `beautifulsoup4`, `trafilatura` and Python XML parsing for news collection; `pandas`/`numpy` for tables and numeric operations; `statsmodels` for regression; `matplotlib` for plots; `PyYAML` for configuration; Ollama for **optional, local-only** model inference. No paid LLM/API calls were used.

## Local LLM choice, constrained hardware, and future scaling

**What was actually tested.** Development took place on a personal Mac with limited available memory (approximately **5 GB available** during the pilot). To stay within this practical resource budget and avoid paid inference, the experiment used [Ollama](https://ollama.com/) to run **`qwen2.5:1.5b` locally**, after initially experimenting with **`qwen2.5:0.5b`**. The 1.5B model was a **hardware-constrained proof of concept**, **not a claim that 1.5B is state of the art or the optimal finance model**. The model itself is not trained or fine-tuned by this project.

**Implementation detail.** `Scripts/12_local_llm_labels.py` calls the local Ollama chat endpoint `http://127.0.0.1:11434/api/chat` via HTTP and asks for a constrained JSON object. In the reported configuration it used `temperature=0`, `num_ctx=2048`, `num_predict=240`, and an approximately **1,000-character** article input budget. Python constructs up to **five numbered original-text excerpts**; the model chooses an `evidence_id`, and Python retrieves that exact excerpt instead of trusting a model-generated quotation. It records the model ID, prompt version, input hash, retries, response errors and flags for invalid evidence or scores. This limits some formatting errors, **but does not establish that a selected quote supports the economic interpretation**.

**Measured limitations.** In the 30-article NVIDIA issuer-news pilot using the 1.5B model, **9/30** final labels passed structural/evidence checks, **3/30** required review, and **18/30** failed, often because the model generated a score outside the allowed `[-1,+1]` range (such as `4`). Economic-channel labels also repeatedly collapsed to `Investor_Relations`, and some chosen evidence excerpts were truncated. Invalid scores were **kept missing**, not clipped to valid numbers. These model labels **were not used as validated predictors in the reported market regression**; that regression used LM dictionary measurements. Small-model output should not be equated with research-grade economic truth.

**Future work (not implemented or benchmarked here):** compare larger local models (e.g., 3B/7B and larger, where adequate RAM/VRAM/compute is available), use stronger event/category taxonomies, obtain independent blinded human labels, evaluate per-class agreement and calibration, and investigate better publication-time alignment and out-of-sample evaluation. Any future cloud or paid model experiments would be explicitly labeled separately from this **zero-paid-API** baseline. Larger models may help, but their superiority has **not** been established by this pilot.

**Reproduce the exact reported model choice:**

```bash
# Install Ollama from https://ollama.com/ first.
ollama pull qwen2.5:1.5b
# Optional; the default third-party pipeline runs LM scoring without Ollama:
python Scripts/16_auto_news_research.py \
  --ticker NVDA --query NVIDIA --days 30 --max-external 5 \
  --local-llm --llm-model qwen2.5:1.5b
```

For the historical issuer-news runner, **explicitly specify** `--llm-model qwen2.5:1.5b`; the older runner retains a different legacy default. Available memory and model performance depend on local hardware, and a fresh online crawl will not necessarily yield the same news articles.

## Data sources and exact pilot date ranges

The pilot uses **publicly accessible third-party data acquired from the original providers**. These are not included in the GitHub repository; users must download them under the providers' terms.

### Historical market prices (Nasdaq)

| Local file | Instrument | Original download page | Historical sample window (inclusive) | Frequency / price field |
|---|---|---|---|---|
| `Inputs/prices/NVDA.csv` | NVIDIA Corporation common stock (`NVDA`) | [Nasdaq NVDA Historical Data](https://www.nasdaq.com/market-activity/stocks/nvda/historical) | **2021-11-05 → 2026-11-04** | Daily, `Close/Last`, USD |
| `Inputs/prices/QQQ.csv` | Invesco QQQ Trust, Series 1 ETF (`QQQ`), used as the benchmark | [Nasdaq QQQ Historical Data](https://www.nasdaq.com/market-activity/etf/qqq/historical) | **2021-11-05 → 2026-11-04** | Daily, `Close/Last`, USD |

**Observed pilot coverage:** After joining `NVDA` and `QQQ` by date, the original empirical dataset contained **1,254 matched trading sessions**, from **November 5, 2021** through **November 4, 2026**. This describes the original historical download and its matched sample, not a guarantee that a fresh download will have identical rows. Preserve provider/version, raw files and `07_price_audit.json` (including hashes) for exact reproduction.

**Price definition:** Nasdaq-exported `Close/Last` is **not cash-dividend-adjusted total return**. The pilot estimates close-to-close **price-return** differences (`NVDA` minus `QQQ`), not dividend-reinvested or risk-adjusted abnormal returns. Corporate-action/split handling should be checked against the provider's methodology. Do not substitute adjusted closes without explicitly documenting a changed specification.

**How to obtain:** Open each Nasdaq page, download its daily historical CSV covering the stated dates (when available), rename the exported files to `NVDA.csv` and `QQQ.csv`, and place them in `Inputs/prices/`. The parser accepts a `Date` column plus `Close/Last` (or a supported alternative). Nasdaq page availability, date-range controls, and downloadable coverage may change; see [Nasdaq Historical Data](https://www.nasdaq.com/market-activity/quotes/historical).

### Finance-specific dictionary (University of Notre Dame)

| Local file | Source / authors | Exact version | Official page |
|---|---|---|---|
| `Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv` | Loughran–McDonald financial sentiment Master Dictionary, University of Notre Dame SRAF | **1993–2025** CSV (official page updated **March 2026**) | [Notre Dame — Loughran–McDonald Master Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) |

The `1993–2025` in the filename identifies the **dictionary version/coverage**, **not** the study's stock-price dates. Download the CSV with exactly this filename from the official page and save it under `Inputs/`. The provider says its word lists are free for academic research; permission to use is distinct from permission to republish the full dictionary.

### News sources and the separate news window

* First-party issuer announcements: [NVIDIA Newsroom](https://nvidianews.nvidia.com/); `Inputs/config.yaml` sets the original **news-study window** to **2026-08-01 through 2026-11-04**, which is **different from the five-year market-price window**. The observed pilot captured 30 announcements, not every release in that window.
* Automatically discovered external articles: public search/publisher RSS feeds (including TechCrunch and CNBC in the pilot), followed by permitted publisher-text extraction. The November 5, 2026 external trial retrieved 2 full texts. New RSS runs select a rolling window and will not necessarily reproduce those same articles.

## Quick start (macOS/Linux)

Python 3.11–3.12 recommended (newer versions may work but have not been independently validated). Commands assume you are in the repository root.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

**Install required research inputs locally (not redistributed):**

* Official `Loughran-McDonald_MasterDictionary_1993-2025.csv` in `Inputs/` — download from the [Notre Dame SRAF site](https://sraf.nd.edu/loughranmcdonald-master-dictionary/).
* For historical price tests/analysis, Nasdaq daily CSVs at `Inputs/prices/NVDA.csv` and `Inputs/prices/QQQ.csv` covering **2021-11-05 to 2026-11-04** (original 1,254 matching trading sessions). Format: `Date,Close/Last`, `Date,Close`, or `Date,Adj Close`; dates may be MM/DD/YYYY or ISO. **Use the original raw `Close/Last` data to match the pilot specification**; price adjustments must be verified with the provider.

### One-command external news → LM measurement (no preselected article URLs)

```bash
python Scripts/16_auto_news_research.py \
  --ticker NVDA --query NVIDIA --days 30 --max-external 5
```

Writes a new `Results/NVDA/ExternalAuto/<UTC_run_id>/` directory. The code tries multiple public RSS feeds and records failures separately from empty feeds. **It does not modify** the historical `LATEST.txt` or automatically add current articles to a past return regression.

To rerun only the LM measurement from a previously collected auto-RSS run, without new network requests:

```bash
python Scripts/16_auto_news_research.py --ticker NVDA --existing-run YOUR_UTC_RUN_ID
```

For optional **local-only** LLM output, install [Ollama](https://ollama.com/) and pull `qwen2.5:1.5b`, then add `--local-llm --llm-model qwen2.5:1.5b`. Its output is an audit artifact, **not** independently validated truth.

### Original issuer-news / market pilot

```bash
python run_all.py --mode demo
python run_all.py --mode live --ticker NVDA --max-articles 10 --collect-only
# After installing valid market CSVs and reviewing the run context:
python run_all.py --mode live --ticker NVDA --resume
```

`Inputs/config.yaml` controls the historical study window and other data collection settings. Use original URLs and provenance, not synthetic results, for live research. The demo is intentionally synthetic and must never be represented as empirical evidence.

## Observed pilot results (not promises of performance)

The November 5, 2026 pilot yielded:

* **First-party historical text:** 30 NVIDIA newsroom articles, with LM polarity hits in 29; 18 daily signal observations.
* **Exploratory NVDA-minus-QQQ close-to-close price-return regression:** Pearson correlation −0.0353; OLS sentiment coefficient −0.00174; HC1 SE 0.00986; exploratory *p* ≈ 0.860; R² ≈ 0.00125. No demonstrated association. **This is not an abnormal-return, causal, or trading-profit result.**
* **Local Qwen2.5 1.5B, 30 articles:** 9 passed structural/evidence checks, 3 required review, and 18 failed (primarily invalid numeric scores). A pass is **not a semantic-accuracy score**.
* **Automatically discovered third-party text:** 6/8 RSS feeds operational, 2 distinct relevant articles discovered, 2 publisher bodies retrieved, 2 with LM polarity matches. Observed LM scores: +0.142857 (TechCrunch Box/Nemotron), +0.500000 (CNBC Moonshot/Blackwell). These are not market-return predictions.
* **Reference coding:** 10 texts received *AI-assisted* reference labels, which do **not** constitute independently blinded human ground truth.

See [`docs/RESEARCH_REPORT.md`](docs/RESEARCH_REPORT.md), [`docs/pilot_metrics_2026-11-05.json`](docs/pilot_metrics_2026-11-05.json), and the two-news summary [`docs/external_lm_results_2026-11-05.csv`](docs/external_lm_results_2026-11-05.csv).

### Historical issuer-news scatterplot

![NVDA-minus-QQQ exploratory price returns against daily LM score](docs/figures/09_signal_vs_return.png)

## Reproducibility and ethics

* Complete code is included, but **raw third-party text, vendor-supplied market data, and the official LM dictionary are not redistributed**. Supply these files under their own terms.
* Feed/HTML changes and site/network restrictions can prevent future runs from finding exactly the same articles. Original pilot results are summarized in `docs/`; this is **reproducibility documentation, not a guarantee of identical online data**.
* Model output validity and textual evidence are audited separately from economic interpretation.
* Publication times are not verified intraday, therefore externally discovered news must **not** be blindly joined to same-day returns.
* Automated fetching must respect website terms, `robots.txt`, access controls and rate limits. No ban or paywall circumvention is implemented.

## Repository layout

```text
Scripts/                Python discovery, extraction, LM, LLM, and regression modules
Inputs/config.yaml      Data collection settings
Inputs/prices/          Local-only raw price files (excluded from Git)
Results/                Per-run outputs and audits (excluded from Git)
tests/                  Offline unit tests
docs/                   Release-level aggregate research evidence, without raw text
run_all.py              Historical issuer-news pipeline
```

For commands, caveats, data provenance and run checks, see [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md). For macOS/GitHub publishing steps, see [`docs/发布到GitHub_中文指南.md`](docs/发布到GitHub_中文指南.md). See `Python.md` for additional legacy instructions.

**License:** No license is granted by this draft repository; the author should choose a code license before public reuse. Data source copyright and usage permissions are separate from code licensing.
