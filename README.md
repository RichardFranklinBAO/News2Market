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

## Quick start (macOS/Linux)

Python 3.11–3.12 recommended (newer versions may work but have not been independently validated). Commands assume you are in the repository root.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

**Install required research inputs locally (not redistributed):**

* Official `Loughran-McDonald_MasterDictionary_1993-2025.csv` in `Inputs/` — see <https://sraf.nd.edu/loughranmcdonald-master-dictionary/> for terms and official download.
* For historical price tests/analysis, legitimate CSV files at `Inputs/prices/NVDA.csv` and `Inputs/prices/QQQ.csv`. Format: `Date,Close/Last`, `Date,Close`, or `Date,Adj Close`; dates may be MM/DD/YYYY or ISO. Price adjustments must be verified with the provider.

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
