# Reproducibility and source integrity

## 1. Test the code without any internet or proprietary inputs

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q Scripts run_all.py
```

Offline tests cover parsing, source selection, LM scoring, synthetic price joining, local model schema/evidence validation, and external RSS/bridge filtering. The historical five-year integration test is **skipped if non-redistributed third-party CSVs are absent**.

## 2. Obtain legitimate research data

**Exact pilot data provenance:**

| Input | Official source | Historical period or version | Local path |
|---|---|---|---|
| NVDA daily price | [Nasdaq NVDA historical page](https://www.nasdaq.com/market-activity/stocks/nvda/historical) | **2021-11-05 to 2026-11-04**, daily USD `Close/Last` | `Inputs/prices/NVDA.csv` |
| QQQ daily benchmark price | [Nasdaq QQQ historical page](https://www.nasdaq.com/market-activity/etf/qqq/historical) | **2021-11-05 to 2026-11-04**, daily USD `Close/Last` | `Inputs/prices/QQQ.csv` |
| Loughran–McDonald Master Dictionary | [University of Notre Dame SRAF](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) | `Loughran-McDonald_MasterDictionary_1993-2025.csv` (official page updated March 2026) | `Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv` |

The historical dataset had **1,254 NVDA/QQQ date-matched trading sessions**. The **news collection configuration** is a different period, **2026-08-01 to 2026-11-04**. For an exact historical regression reproduction, preserve the original price CSVs and captured news snapshot; newly fetched articles and downloaded price revisions can differ. The original price field `Close/Last` is **not adjusted for cash dividends**; do not label these as total returns. Publication-time uncertainty limits return interpretation.

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
