# Reproducibility and Data Provenance

The **single current entrypoint** is `python -m news2market --web` (or `python -m news2market --ticker NVDA --news-days 30 --price-years 5`). Python 3.11–3.12 is recommended. The app is a local-only dashboard at `127.0.0.1:8765`; use `--port 8766` if that port is occupied.

## Clean installation

```bash
git clone https://github.com/RichardFranklinBAO/News2Market.git
cd News2Market
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m news2market --web
```

A private repository requires collaborator access. Run the tests before beginning any external crawl; the 15 current tests were all passing in the build environment with the valid official LM dictionary, while the final data-dependent integration test is skipped when the dictionary is absent.

## Research inputs

* **Financial lexicon:** Obtain `Loughran-McDonald_MasterDictionary_1993-2025.csv` from [Notre Dame SRAF](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) and save at `inputs/` under exactly that filename. The app checks it before making news requests; the lexicon is not included in GitHub.
* **Market prices:** Official Nasdaq historical CSVs for the chosen `NVDA`, `AAPL`, or `GOOGL` stock **and QQQ**. See direct provider links in the root README. The files must contain `Date` and `Close/Last`; select and import them in the dashboard after confirming source and ticker. The app records SHA-256, source-confirmation, observed date coverage and row counts. Neither Yahoo nor an unauthorized Nasdaq crawler is used.
* **Article bodies:** New issuer/publisher announcements are discovered via permitted public feeds and HTML; original third-party full texts are not redistributed with the repo. The exact same historical news snapshots cannot be reconstructed from their URLs alone.

The historical NVIDIA pilot used NVDA and QQQ CSVs with **1,254 matched dates from 2021-11-05 to 2026-11-04**. The original issuer news was collected from a different configured study window, **2026-08-01 to 2026-11-04**. A fresh online run has a rolling news window and will not guarantee identical articles or returns. Nasdaq `Close/Last` is not dividend-adjusted total return.

## Verify an actual research run

The app writes one directory per selected ticker and UTC run ID:

```text
Results/<TICKER>/Runs/<UTC_RUN_ID>/
    research_report.json     # status, coverage and warnings
    news_audit.json          # source/collection audit
    news_summary.csv         # article-level measures
    05_lm_labels.csv         # official financial lexicon labels
    07_prices.csv            # paired real prices
    07_price_audit.json      # market input provenance
```

A successful run means the app processed the available, legally accessible data and emitted audits. If no texts qualify, it records zero articles rather than inventing them. If there are too few matched signal days, it does not fabricate a regression. Model labels and causal claims require **separate external validation**.

## Methods and limitations

* News: company-specific first-party RSS/HTML plus multi-publisher feeds, normalized URLs, headline/summary relevance filters, cautious text extraction and date-quality warnings. Not a complete historical archive.
* NLP: count positive, negative and uncertainty LM words per 1,000 tokens; secondary `(P−N)/(P+N)` polarity with missing-value handling. Heuristic categories are not validated investor expectation surprises.
* Local LLM (optional): Ollama `qwen2.5:1.5b`, structured JSON/evidence ID checks; no model weights or paid cloud API are shipped. Formatting correctness is not semantic reliability.
* Market: selected stock-minus-QQQ close-to-close price-return differences, conservative next-session alignment when article times are day-level; exploratory HC1 OLS if data suffice. No factor adjustments, backtesting or causal assertions.
* Clean clone: test with the dictionary and both CSVs installed **inside the freshly cloned project** rather than relying on an adjacent older project. Check the generated audit files.

See [Research Report](RESEARCH_REPORT.md) for the preserved historical NVIDIA pilot evidence. Test fixtures are synthetic only and are never presented as real empirical results.
