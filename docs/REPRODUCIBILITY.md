# Reproducibility: News2Market v3.1 and historical v2 pilot

**Current public-code entrypoint:** `python run_v3.py --web`. Install dependencies with `python -m pip install -r requirements_v3.txt`. The dashboard runs locally on `http://127.0.0.1:8765` and supports NVDA, AAPL and GOOGL (Alphabet Class A), benchmarked to QQQ.

**Required inputs:** The official LM 1993–2025 dictionary must be placed in `Inputs/` or validated and reused from a local sibling `News2Market` project. The repo does **not** redistribute the dictionary; use https://sraf.nd.edu/loughranmcdonald-master-dictionary/. A missing/invalid dictionary is detected before the news crawl. Selected company and QQQ must also have separately obtained official Nasdaq `Date,Close/Last` CSVs, imported via the dashboard. This version makes **no Yahoo calls** and does **not** automatically scrape Nasdaq.

**Main run checks:** `python -m unittest discover -s tests -v`; `python run_v3.py --ticker NVDA --news-days 30 --price-years 5` for a real run with authorized local data and permitted network access. Three-company offline fixtures and unit tests do not constitute online validation. The original 30 NVIDIA news articles are not republished.

**Limits:** News may be missing; official releases and editorial coverage are not interchangeable; article timestamps are often day-level; raw `Close/Last` is not dividend-adjusted total return; LM and local Qwen2.5 1.5B measurements are not validated market-surprise indicators; HC1 OLS is exploratory. See the `Limitations and resource-constrained development` section of the root README.

---

## Legacy research and reproduction notes

# Reproducibility and source integrity

## 1. Test the code without any internet or proprietary inputs

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q Scripts run_all.py
```

Offline tests cover parsing, source selection, LM scoring, synthetic price joining, local model schema/evidence validation, and external RSS/bridge filtering. The historical five-year integration test is **skipped if non-redistributed private CSVs are absent**.

## 2. Obtain legitimate research data

* Obtain the official Loughran–McDonald 1993–2025 master dictionary and place it under `Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`; check your usage eligibility before downloading.
* Optional historical empirical mode requires authentic closing-price CSVs in `Inputs/prices/NVDA.csv` and `Inputs/prices/QQQ.csv`; review split/dividend methodology and preserve data-source provenance.
* Access to websites/feeds can change. Ensure your automated requests comply with site policies; 429/403 are **not** instructions to bypass protections.

## 3. Reproduce the live third-party pipeline (new crawl)

```bash
python Scripts/16_auto_news_research.py --ticker NVDA --query NVIDIA --days 30 --max-external 5
```

Check `Results/NVDA/ExternalAuto/<RUN_ID>/16_research_audit.json` for `lm_status`, exclusions, eligible counts and the intraday-time warning. The `16_external_lm_summary.csv` links to the article sources; no original publisher body is redistributed in this repo.

Optional LLM (Ollama installed locally with `ollama pull qwen2.5:1.5b`):

```bash
python Scripts/16_auto_news_research.py --ticker NVDA --query NVIDIA --days 30 --max-external 5 --local-llm --llm-model qwen2.5:1.5b
```

Local model output is not automatically added to regression and **must be independently quality-checked**.

## 4. Re-score a preserved run (no new web collection)

```bash
python Scripts/16_auto_news_research.py --ticker NVDA --existing-run <RUN_ID>
```

A previously captured `15_external_articles.csv` and `15_external_summary.json` must exist under the corresponding `Results/NVDA/ExternalAuto/<RUN_ID>` directory. The public repository does **not** contain full publisher text and therefore cannot reconstruct the exact past scores from URLs alone.

## 5. What is and is not reproducible

| Stage | What a clean clone can do | What it needs for identical historical output |
|---|---|---|
| Offline code checks | Full offline tests, no provider access | Python dependencies |
| RSS and publisher extraction | New live run on currently accessible feeds | Original source pages must remain available/accessible |
| LM sentiment | Score fetched articles | Official dictionary with matching version and exact captured text |
| Local Qwen | Generate exploratory labels | Matching Ollama model, prompt, model runtime and original text; deterministic output not guaranteed |
| Market regression | Execute if configured historical data are supplied | Legitimate source-matched price CSV, article snapshots, preserved run config |

## 6. Pilot provenance / key constraints

See `docs/pilot_metrics_2026-11-05.json` and `docs/RESEARCH_REPORT.md`. Raw price input: 1,254 paired sessions, 2021-11-05 to 2026-11-04, unadjusted Close/Last. Historical issuer news 30 articles and 18 days used for regression. External trial 2 of 2 collected articles scored with LM; first-availability timestamp unknown. No independent human validation.

## 7. GitHub publication checks

1. Do **not** commit downloaded LM dictionaries, downloaded market data, publisher news text, secrets or personally identifying local filesystem paths.
2. Review publisher, price-feed and LM usage terms before sharing any derived source artifacts.
3. Choose a code license (this draft does not grant one automatically).
4. Push only after `git status`, `git diff --cached --stat` and `git diff --cached` show no restricted files.
