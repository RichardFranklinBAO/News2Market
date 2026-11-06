# One-Command News + SEC + LM + Market Research (v0.3)

The original standalone Workflow A dashboard and Workflow B `research sec`
are preserved. The new root-level **`run_all.py`** performs the steps in one run;
there is no need to locate NEWS_RUN_ID, SEC_RUN_ID, or merge CSVs manually.

## First-time setup (fresh ZIP or clone)

From the project directory on Mac, install dependencies:

```bash
cd ~/Downloads/News2Market-main
python -m pip install -r requirements.txt
```

The official Loughran–McDonald 1993–2025 dictionary must be installed locally
at `inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`. Download it from
[Notre Dame SRAF](https://sraf.nd.edu/loughranmcdonald-master-dictionary/).
It is not bundled in the repository and should never be committed.

SEC requests require a truthful real name and contact email:

```bash
export N2M_SEC_USER_AGENT="Your Real Name your-real-email@example.com"
```

## One command

```bash
python run_all.py --ticker NVDA
```

**Optional explicit date window and price-source selection:**

```bash
python run_all.py --ticker NVDA --start 2026-01-01 --end 2026-11-06 \
  --max-news 15 --max-filings 50 --prices auto
```

- `--prices auto` (default): try adjusted historical Yahoo daily data via the
  unofficial `yfinance` library, then fall back to **previously user-verified**
  Nasdaq CSVs; failure of both is an explicit error. When Yahoo data are stale
  by more than ten calendar days, the automatic mode prefers the fallback
  rather than pretending that downloaded prices are current.
- `--prices yahoo`: use Yahoo only; a failure is explicit. No silent fallback.
- `--prices nasdaq`: use an already imported, hash-verified pair at
  `inputs/prices/<TICKER>.csv` and `inputs/prices/QQQ.csv`, or import both
  with `--stock-csv /path/to/stock.csv --qqq-csv /path/to/qqq.csv --confirm-nasdaq`.
- `--news-days 90` is the default discovery window; `--start` and `--end`
  override it. `--max-news 15` and `--max-filings 50` are the defaults.
  The SEC collector currently accepts at most 100 filings per call, from recent
  submissions (not complete historical archives).

**Data-source caveat:** `yfinance` uses Yahoo Finance data through an
unofficial open-source adapter, not an official paid/contracted price feed.
It can fail or change without notice; check access terms. Its
`auto_adjust=True` historical close semantics differ from **raw**
Nasdaq `Close/Last`. Each run records the selected provider, basis, hashes,
coverage, and whether fallback occurred. Neither source is silently treated
as the other.


## Interactive US ticker mode (new)

To select a U.S.-exchange-listed *stock* in the Terminal, simply run:

```bash
python run_all.py
```

The program prompts `Stock ticker:`. Type `NVDA`, `AAPL`, `MSFT`,
`AMD`, `TSLA`, etc., or specify `python run_all.py --ticker MSFT`.
It cross-checks the exact ticker against current **SEC CIK/company/exchange**
mappings and **Nasdaq Trader** Nasdaq/other-listed symbol directories.
ETF and test-issue flags are rejected, along with common warrant/right/preferred
patterns. A symbol that cannot be confirmed from live/recent official registries
is rejected rather than guessed. The symbol cache expires after 24 hours;
this check does not prove historical identity, article-level relevance, or
uninterrupted listing. A valid current US-listed ticker without a SEC CIK
cannot currently be processed by the SEC workflow.

The registry lookup and pricing can require external web access and can fail
under site access restrictions. The original AAPL/GOOGL/NVDA dashboard remains
a legacy three-company interface; flexible ticker selection is available via
`run_all.py`.

## Manual Nasdaq CSV naming and automatic import

**Canonical storage location:** `inputs/prices/`, *lowercase* `inputs` and
`prices`. Files must be named using the uppercase exact selected symbol:

```text
inputs/prices/
  NVDA.csv
  MSFT.csv
  AAPL.csv
  QQQ.csv
  SOURCE_MANIFEST.json
```

There is **one file per stock**, not one file per trade date. `QQQ.csv` is
the common comparison benchmark. The imported files are accompanied by a
generated SHA256 provenance manifest. A CSV simply copied and renamed without
a manifest is not automatically accepted as verified data, because the CSV
itself does not prove which ticker it belongs to.

You can download any two corresponding Historical Data CSVs from Nasdaq; you do
**not** need to rename the original `HistoricalData_*.csv` exports. Import
them using an explicit source-attributed, one-command run:

```bash
python run_all.py --ticker MSFT --prices nasdaq \
  --stock-csv "$HOME/Downloads/HistoricalData_msft.csv" \
  --qqq-csv "$HOME/Downloads/HistoricalData_qqq.csv" \
  --confirm-nasdaq
```

The command checks both files before writing either. It then saves canonical
`inputs/prices/MSFT.csv` and `inputs/prices/QQQ.csv`, records original SHA256
hashes and the user's Nasdaq source attestation, and runs the entire workflow.
When CSVs are explicitly supplied, they take precedence over Yahoo.
When the user wants no manual price imports, use the default `--prices auto`.

**Nasdaq CSV format accepted by the one-command importer:**

```csv
Date,Close/Last,Volume,Open,High,Low
11/04/2026,$205.00,100000,$204.00,$207.00,$203.00
11/03/2026,$204.00,110000,$203.00,$206.00,$202.00
11/02/2026,$202.00,120000,$201.00,$204.00,$200.00
```

Required columns are `Date` and `Close/Last` (case-insensitive punctuation);
extra columns are allowed. Dates may be `MM/DD/YYYY` or `YYYY-MM-DD`,
prices must be finite and positive, and trading dates must not duplicate.
Use original Nasdaq downloads, not fabricated values or renamed Yahoo data.
Price CSV exports often omit embedded ticker identifiers; the user explicitly
assigns the ticker at import. Both files must have at least three distinct
observations. For meaningful 1/3/5-day forward returns, include dates that
extend beyond news and SEC publication dates.

**Important:** Raw Nasdaq `Close/Last` is not dividend-adjusted. It must not
be silently combined with Yahoo's adjusted closes inside a single run. Data
provider, adjustment semantics, price coverage and source hashes are recorded
in each run's audit.

## Execution and outputs

1. Find full-body issuer/publisher news automatically (no manually seeded URLs).
2. Collect identified 8-K/10-Q/10-K primary SEC documents with a declared
   User-Agent. Combine and remeasure News + SEC using the *same* LM dictionary
   with the existing identity and text-quality checks.
3. Acquire verified stock/QQQ historical closes using the selected provider.
4. Align events with future relative stock-versus-QQQ returns and attempt the
   time-ordered source-specific holdout diagnostic.

All inputs and outputs are grouped under:

```text
Results/NVDA/Unified/<UTC_RUN_ID>/
  unified_audit.json
  news_articles.csv
  news_collection_audit.json
  price_audit.json
  prices/NVDA_yahoo_adjusted.csv
  prices/QQQ_yahoo_adjusted.csv
  stages/NVDA/Research/<SEC_RUN_ID>/
    sec_collection_audit.json
    sec_data_quality_report.md
    identity_audit.json  # when news identity audit applicable
    research_features.csv
    research_audit.json
  market/
    market_event_alignment.csv
    market_alignment_audit.json
    market_alignment_report.md
    market_signal_validation.json
    market_holdout_predictions.csv
```

Some files are conditional: Yahoo CSVs are absent when only Nasdaq data are
used; `research_features.csv` is not produced when no complete text is
available. A rejected/failed stage preserves a partial `unified_audit.json`.

## What one-command execution does NOT establish

A successful pipeline is not a statistically validated Buy/Sell classifier.
Recent RSS feeds cannot reliably backfill arbitrarily old articles. SEC recent
submissions do not necessarily cover all historical filings, and primary
documents can omit economically material exhibits. A longer `--start`
window does **not** guarantee a larger independent news sample.

The existing experimental validation requires at least 40 distinct informative
signal days for a single chronological holdout, and even 40 is only a
conservative engineering threshold, not evidence of statistical power.
When data are insufficient, the program honestly reports
`insufficient_evidence` and does **not** fit a model or fabricate predictions.
Date-only availability assumptions, QQQ constituent overlap, source
nonstationarity, and incomplete corporate-action audit remain limitations.

## Reproducibility and offline verification

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Offline synthetic tests confirm command wiring and fallback logic, not live
Yahoo/SEC response behavior. Real access and data provenance should be
inspected in the output audits after each actual run.
