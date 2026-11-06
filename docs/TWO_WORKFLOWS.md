# News2Market — Two Workflows and Reproduction Checklist

These are two independent ways to use the same codebase. Choose **Workflow A** for a news/market report and **Workflow B** for a SEC text-measurement audit. Neither requires paid APIs. The optional Ollama/Qwen model is not necessary.

## One-time setup on a Mac (for either workflow)

Use Python 3.11 or 3.12. A fresh Git clone is preferable to an older ZIP:

```bash
cd ~/Desktop
git clone https://github.com/RichardFranklinBAO/News2Market.git News2Market_Check
cd News2Market_Check
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests should finish with **OK**; a test dependent on the official dictionary may be skipped if the file is absent. Offline unit tests alone do not establish real SEC or news availability.

Obtain the official Loughran–McDonald 1993–2025 CSV from [Notre Dame SRAF](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) and save it with this exact path:

```text
inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv
```

Do not commit the dictionary or third-party market/news source data. This is required for **both** LM analysis modes.

## Workflow A — News Collection + Nasdaq Market Report

**What it does:** select NVDA/AAPL/GOOGL → discover issuer and publisher news → extract eligible text → calculate LM financial-text measurements → align with company and QQQ market closes → output an exploratory report. This is **not** a validated market predictor.

1. Download the selected company's daily historical CSV and **QQQ** CSV separately from their official Nasdaq pages: [NVDA](https://www.nasdaq.com/market-activity/stocks/nvda/historical), [AAPL](https://www.nasdaq.com/market-activity/stocks/aapl/historical), [GOOGL](https://www.nasdaq.com/market-activity/stocks/googl/historical), and [QQQ](https://www.nasdaq.com/market-activity/etf/qqq/historical). Check that both CSVs have `Date` and `Close/Last`. The app **does not** automatically download Nasdaq data; it also does not use Yahoo.
2. Launch the English web interface from the cloned repository:

   ```bash
   source .venv/bin/activate
   python -m news2market --web --port 8766
   ```

3. Open **http://127.0.0.1:8766** in your browser. Select NVIDIA / Apple / Google. Under **Nasdaq Historical Data**, select the company CSV and QQQ CSV, confirm that they were obtained from Nasdaq, and click **Import selected CSV files**.
4. Verify that **LM Dictionary, selected stock CSV and QQQ CSV** show ready. Choose **30 days** of news, **5 years** of prices and up to **10** articles; keep the optional local LLM off initially. Click **Run research**.
5. Inspect the latest company run folder, e.g. for NVDA:

   ```bash
   open "$(ls -dt Results/NVDA/Runs/*/ | head -n 1)"
   ```

Look for `research_report.json`, `news_audit.json`, `news_summary.csv`, `05_lm_labels.csv`, `07_prices.csv`, and `07_price_audit.json`. Those historically numbered **output artifacts** are preserved for research compatibility; the Python **source script filenames** are now functional names.

**Success criteria:** the actual source and price audits are present, source identity is documented, eligible articles have LM measurements, and any correlation/regression is clearly labeled exploratory. If news sources block requests, no complete article is available, prices end before recent news, or signal days are sparse, a regression may legitimately be absent. Do not treat the existence of a plot as a predictive finding.

## Workflow B — SEC EDGAR Collection + LM Analysis

**What it does:** read official submissions for the selected issuer → select recent 8-K/10-Q/10-K files → optionally retrieve primary document bodies → audit completeness → score only eligible complete body text with the official LM dictionary and produce descriptive TF-IDF features.

**No Nasdaq CSV, dashboard, Ollama or Qwen is needed.**

1. Open Terminal in the repository and activate the Python environment:

   ```bash
   cd ~/Desktop/News2Market_Check
   source .venv/bin/activate
   ```

2. Set a **genuine name and contact email** for SEC's user agent. Do not use the example unchanged:

   ```bash
   export N2M_SEC_USER_AGENT="Your Real Name your-real-email@example.com"
   ```

3. Run a small test. Keep the conservative access limits and stop on HTTP 403/429 (do not bypass access restrictions):

   ```bash
   python -m news2market research sec \
     --ticker NVDA \
     --start 2026-01-01 \
     --end 2026-11-05 \
     --max-filings 5 \
     --fetch-bodies
   ```

4. Open the newest SEC result folder:

   ```bash
   open "$(ls -dt Results/NVDA/Research/*/ | head -n 1)"
   ```

5. Read `sec_collection_audit.json`, `sec_data_quality_report.md`, and `research_audit.json`. Inspect `research_features.csv` if it exists. Check: source is official SEC; CIK matches; counts of extracted, truncated and excluded bodies are plausible; `text_scored_records` equals the number of eligible complete bodies; and eligible records have `lm_text_truncated=False`. The command's `completed_with_limitations` status alone does not prove successful LM scoring.
6. To test other companies, run the same command using `--ticker AAPL` and then `--ticker GOOGL`. Their results are stored independently under `Results/AAPL/Research/` and `Results/GOOGL/Research/`.

**Caveats:** The 1.5 MB response cap and 240,000-character text cap can exclude long filings; truncated documents are not scored as complete text. The current implementation focuses on primary documents and does not systematically retrieve exhibits. SEC acceptance time does not establish the first public market-available instant. For the verified three-company 15-filing pilot, see [SEC Real-Data Validation](SEC_REAL_DATA_VALIDATION_2026-11-06.md).

## Optional Qwen labels

Ollama is a local model-serving runtime. To experiment with optional economic event annotation, [install Ollama](https://ollama.com/download), run `ollama pull qwen2.5:1.5b`, and enable **Local LLM** in the dashboard. These labels are not independently human-validated.
