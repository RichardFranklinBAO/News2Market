# News2Market v3.1 — Nasdaq-Only, English Dashboard

This release removes Yahoo/yfinance completely. The historical-price module consumes only locally imported **official Nasdaq historical CSVs** (`Date` and `Close/Last`). Its UI, controls, logs and outputs are in English.

## Local Mac installation — install side by side

1. Unzip `News2Market_v3_1_Nasdaq_English_Full.zip` into `~/Desktop/projects/`. The old `~/Desktop/projects/News2Market/` must be preserved.
2. Open Terminal:

```bash
cd ~/Desktop/projects/News2Market_v3_1_Nasdaq_English
cp ../News2Market/Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv Inputs/
python -m pip install -r requirements_v3.txt
python run_v3.py --web
```

3. Visit **http://127.0.0.1:8765/** if the browser does not open automatically.
4. Select **NVIDIA / NVDA**, **Apple / AAPL**, or **Google / GOOGL** (Alphabet Class A). The fixed benchmark is **QQQ**.
5. The dashboard automatically checks for *previously verified* Nasdaq NVDA/QQQ files in a sibling `News2Market/Inputs/prices/` folder and copies them locally (the original files are never changed). It verifies the SHA-256 checksums against the sibling's `SOURCE_MANIFEST.json`. If your original project is elsewhere or lacks the manifest, import the files using the dashboard instead.
6. If a price CSV is missing, open the corresponding official Nasdaq historical-data link from the dashboard. Download the CSV for the desired interval and **import each file** (target equity and QQQ) after confirming its source. Do this once; subsequent runs reuse the local file until you choose to update it.
7. Click **Run research**. News discovery and LM analysis proceed automatically. Optional local Qwen labels are disabled by default.

**Important:** Nasdaq's publicly visible download control is not an unrestricted automated data API. This free research prototype does **not** scrape Nasdaq, bypass access restrictions or pretend that manual import is an automated download. An approved/licensed official data-access interface could later replace the one-time user import.

## Historical-data links

| File | Original Nasdaq download page | Original pilot dates |
|---|---|---|
| `Inputs/prices/NVDA.csv` | https://www.nasdaq.com/market-activity/stocks/nvda/historical | 2021-11-05 to 2026-11-04 |
| `Inputs/prices/AAPL.csv` | https://www.nasdaq.com/market-activity/stocks/aapl/historical | Choose requested dates |
| `Inputs/prices/GOOGL.csv` | https://www.nasdaq.com/market-activity/stocks/googl/historical | Choose requested dates |
| `Inputs/prices/QQQ.csv` | https://www.nasdaq.com/market-activity/etf/qqq/historical | 2021-11-05 to 2026-11-04 in the original pilot |

Each manually downloaded file must have **`Date` and `Close/Last` columns**. Nasdaq's raw `Close/Last` is not cash-dividend-adjusted total return. Nasdaq CSVs normally lack an internal ticker identifier, so **the user must confirm ticker identity**. Imports store checksums, timestamps, row counts and the official source URL in the local manifest. Inputs, credentials, and third-party news text are not republished.

## Offline checks

```bash
python -m unittest discover -s tests -p 'test_v3.py' -v
python run_v3.py --ticker NVDA --price-mode auto --news-days 30 --price-years 5
```

A newly downloaded period can have different coverage from the original 1,254-session pilot. Historical-price availability alone does not yield matching news observations. Each live RSS run is contingent on current publisher access and may return zero full-text articles. External news timestamps are day-level only and are **not suitable for same-day causal event-study claims** without further verification.

**No tests of live Nasdaq scraping are included because the application performs none.** Tests cover real Nasdaq CSV reuse/import and synthetic-fixture offline news integration. See `README.md` and `PRICE_SOURCE_NOTE.md`.

## Official LM dictionary prerequisite (must be installed locally)

The official Notre Dame `Loughran-McDonald_MasterDictionary_1993-2025.csv` is not part of this GitHub repository. The dashboard now indicates whether the file is present or available for reuse from a sibling `News2Market` project. A run validates and, where possible, copies that **local** file before attempting to download market or news data. It never downloads or replaces the official dictionary without permission and never uses a mock dictionary for live research.

Official source: https://sraf.nd.edu/loughranmcdonald-master-dictionary/

If the file cannot be located, manually copy it into `Inputs/` and restart the run; a missing or invalid dictionary is now a **preflight** failure, not a failure after collecting news.
