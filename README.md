# News2Market

**Company-aware financial news collection, auditable NLP measures, and exploratory empirical research.**

News2Market is an independent Python research prototype. It collects company-related news and SEC disclosures, converts unstructured text into documented financial variables, checks data quality, and explores links with market outcomes. The unified Terminal runner supports SEC-CIK-verified U.S.-listed stocks through dynamic ticker lookup; the legacy browser dashboard remains limited to NVIDIA (NVDA), Apple (AAPL), and Alphabet (GOOGL).

## Research Motivation and Technical Contributions

**Research question:** How can company news and disclosures be transformed into reproducible measures of financial information—and how reliable are those measures?

| Capability | Implemented work |
|---|---|
| **Web scraping / alternative data** | Issuer newsrooms, third-party RSS/publisher feeds, and official **SEC EDGAR 8-K, 10-Q and 10-K** retrieval. |
| **Dataset construction and cleaning** | Firm/CIK checks, deduplication, source URLs, publication dates, document hashes, missingness and extraction audits. |
| **Python NLP and AI** | Official **Loughran–McDonald** financial word frequencies and polarity; descriptive **TF-IDF**; optional experimental local **Ollama/Qwen2.5 1.5B** event labels. |
| **Statistical research and reporting** | Stock/QQQ data alignment, descriptive correlation and HC1 OLS, quality tests, reproducible reports and negative findings. |

### Observed results

- **Real SEC validation (Nov 6, 2026):** 15 company filings across NVDA/AAPL/GOOGL; **11** primary-document bodies passed local completeness checks and were scored with LM; **4** truncated bodies were excluded. All **9 sampled 8-K primary files** were retrieved; attachments were not systematically collected. [Audit report](docs/SEC_REAL_DATA_VALIDATION_2026-11-06.md).
- **Historical NVIDIA news pilot:** 30 announcements, 18 dated signal days; exploratory NVDA–QQQ return association **r = −0.0353, HC1 p ≈ 0.8602**. **No statistically significant relationship found.** [Research report](docs/RESEARCH_REPORT.md).

This demonstrates **research data engineering and text-measurement integrity**, not validated market forecasting or causal identification.

## Fully automatic historical stock prices (v0.4)

**No manual CSV needed when a working market-data API is configured.** The same
interactive `python run_all.py` automatically attempts a SHA256-checked local
cache, then a configured **Tiingo** API, a configured **Twelve Data** API,
unofficial Yahoo Finance, and finally an already user-confirmed local Nasdaq
pair. Failed providers do not silently supply synthetic prices or mixed
stock-versus-QQQ price adjustment bases.

One-time setup (use either market-data provider's account/API key):

```bash
cd ~/Downloads/News2Market-main
python -m pip install -r requirements.txt
export N2M_SEC_USER_AGENT="Your Real Name your-real-email@example.com"
export TIINGO_API_KEY="YOUR_PRIVATE_TIINGO_TOKEN"
# Alternatively: export TWELVEDATA_API_KEY="YOUR_PRIVATE_TWELVE_DATA_KEY"
python run_all.py
```

The program prompts for a current US exchange-listed stock ticker and collects
the paired stock/QQQ adjusted close series automatically. **Never commit API
tokens**; they are read from environment variables. If all API attempts fail,
manual Nasdaq imports remain a last resort. Historical news full-body coverage
and independent forward-return inference remain separate limitations.

See [automatic API/provider setup and limitations](docs/ONE_COMMAND_WORKFLOW.md).

## Start here: where to put downloaded Nasdaq CSVs

**Easiest method: leave the original Nasdaq files in `~/Downloads/`.** You do not need to rename or move them yourself. For a TSLA study, download **both TSLA and QQQ** historical CSVs directly from Nasdaq, then run from the project folder:

```bash
cd ~/Downloads/News2Market-main
export N2M_SEC_USER_AGENT="Your Real Name your-real-email@example.com"
python run_all.py --ticker TSLA --prices nasdaq \
  --stock-csv "$HOME/Downloads/HistoricalData_TSLA.csv" \
  --qqq-csv "$HOME/Downloads/HistoricalData_QQQ.csv" \
  --confirm-nasdaq
```

Replace the filenames above with your **actual downloaded filenames** (case matters). The files must be genuine Nasdaq exports; `--confirm-nasdaq` records your attestation of their source. This command verifies and **automatically copies** them into the project:

```text
News2Market-main/
  inputs/
    Loughran-McDonald_MasterDictionary_1993-2025.csv
    prices/
      TSLA.csv
      QQQ.csv
      SOURCE_MANIFEST.json
```

**For later runs of the same ticker:** if the verified CSVs are already in `inputs/prices/`, just run:

```bash
python run_all.py --ticker TSLA --prices nasdaq
```

The project **requires the generated `SOURCE_MANIFEST.json`** to verify local CSV hashes and the selected ticker. Merely copying/renaming a CSV into `inputs/prices/` without using the import command is **not sufficient**.

**Required Nasdaq CSV headers:** `Date` and `Close/Last`. `MM/DD/YYYY` or `YYYY-MM-DD` dates; price values such as `$245.50`. Columns such as `Volume`, `Open`, `High`, `Low` may remain. At least 3 unique valid dates are required; for meaningful analysis, get a multi-year history including future close dates after the text events. CSV contents alone do not certify the ticker; your explicit import assigns it. Raw Nasdaq prices are not dividend-adjusted.

**Alternative:** `python run_all.py --ticker TSLA --prices auto` tries unofficial Yahoo Finance adjusted closes and falls back to an *already verified* local Nasdaq pair. If Yahoo is rate-limited and you have not imported TSLA + QQQ, the runner stops and explains the missing files. See [full guide](docs/ONE_COMMAND_WORKFLOW.md).

## One-command unified workflow (v0.3)

From the project root, install dependencies and provide a genuine SEC User-Agent:

```bash
python -m pip install -r requirements.txt
export N2M_SEC_USER_AGENT="Your Real Name your-real-email@example.com"
python run_all.py                 # Terminal prompts for an actual US stock symbol
python run_all.py --ticker MSFT   # Or supply an explicit symbol directly
```

The unified runner verifies SEC CIK/exchange and Nasdaq Trader listing records
for the selected ticker; it is no longer limited to NVDA/AAPL/GOOGL.
Canonical user-attested Nasdaq files are stored as
`inputs/prices/<TICKER>.csv` and `inputs/prices/QQQ.csv`, with a SHA256
`SOURCE_MANIFEST.json`. See the full guide for the explicit `--stock-csv`
and `--qqq-csv` import flags. The legacy dashboard remains limited to three
companies.

This runs News collection, SEC document retrieval, unified LM measurement,
automatic adjusted historical stock/QQQ price download via unofficial
`yfinance` (fallback to previously hash-verified local Nasdaq CSVs), and
exploratory market validation **without dashboard clicks or manual run-folder
selection**. The official LM dictionary is still required locally and is not
redistributed. See [complete one-command instructions](docs/ONE_COMMAND_WORKFLOW.md).
Existing Workflow A and Workflow B commands remain available.

## Quick Start

**Choose one of two independent workflows** (both use the official LM dictionary):

| Workflow | Purpose | Additional input | Start |
|---|---|---|---|
| **News + Market Report** | Scrape firm news and explore LM text scores alongside stock/QQQ price returns | Manually imported Nasdaq stock and QQQ CSVs | `python -m news2market --web` |
| **SEC Collection + LM Analysis** | Retrieve and audit 8-K/10-Q/10-K primary documents, then score complete bodies | Genuine SEC User-Agent; **no Nasdaq CSV required** | `python -m news2market research sec ... --fetch-bodies` |

**[Detailed Mac walkthrough for both workflows](docs/TWO_WORKFLOWS.md)** — including exact commands, result locations, and what constitutes a successful check.

**Optional integrated assessment:** Quality-screened News + SEC LM feature records can now be aligned with manually imported Nasdaq stock/QQQ CSVs. The analysis reports **lexical bullish/bearish tendency or insufficient evidence** and *subsequent* 1/3/5-session QQQ-relative returns; **it is not a Buy/Sell signal, verified event study, or trading recommendation**. See [Integrated News–SEC–Market Analysis](docs/INTEGRATED_MARKET_RESEARCH.md).

Python **3.11–3.12** recommended. Install from a fresh clone:

~~~bash
git clone https://github.com/RichardFranklinBAO/News2Market.git
cd News2Market
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
~~~

**External inputs (not included in GitHub):**

- **Official LM dictionary:** obtain [Loughran–McDonald 1993–2025](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) and save as `inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`.
- **For market analysis:** download the selected stock and **QQQ** historical CSVs from [Nasdaq](https://www.nasdaq.com/market-activity) and run the explicit `--stock-csv ... --qqq-csv ... --confirm-nasdaq` command above to auto-import them (no dashboard needed). Alternatively use `--prices auto` for unofficial Yahoo historical prices with a verified-local-Nasdaq fallback. The SEC-only workflow does **not** need stock prices.
- **Optional AI labels:** install [Ollama](https://ollama.com/download) and run `ollama pull qwen2.5:1.5b`. The core LM workflow does not require Ollama or paid APIs.

**Launch the English dashboard:**

~~~bash
python -m news2market --web
# If port 8765 is already in use: python -m news2market --web --port 8766
~~~

Open `http://127.0.0.1:8765`, select a company, import market data, and run the news analysis.

**Run SEC collection and LM analysis:**

~~~bash
# Replace with your REAL name/contact email; comply with SEC fair-access rules.
export N2M_SEC_USER_AGENT="Your Name your-real-email@example.com"
python -m news2market research sec --ticker NVDA \
  --start 2026-01-01 --end 2026-11-05 --max-filings 5 --fetch-bodies
~~~

SEC output is saved under `Results/<TICKER>/Research/<run_id>/` with collection, quality, and research audits plus eligible LM features. Raw text and downloaded data stay local. See [research methods](docs/FINANCIAL_TEXT_RESEARCH.md) and [reproducibility](docs/REPRODUCIBILITY.md).

## Limitations and Future Work

Built on a **personal Mac with free/public-access tools**. Company coverage is limited, news sources can restrict access, large SEC filings may exceed **1.5 MB / 240,000 characters**, and separate exhibits are not fully captured. Partial documents are excluded from complete-body scoring.

Lexicon polarity and optional Qwen labels are **not independently validated economic shocks**. Filing acceptance time does not certify first public availability; the exploratory stock-price analysis is not a rigorous event study. The 15-file SEC pilot is too small for broad inference. Better timestamps, independently labeled corpora, authorized large-scale coverage, and possible **OpenAI API/model comparisons** are future work—not completed features.

## Code and Documentation

~~~text
src/news2market/   Main Python package, SEC research, and English UI
scripts/           News collection and financial-text helper modules
inputs/            Locally installed dictionary and market CSVs
tests/             Offline regression and quality checks
docs/              Real-data audits, research reports, full methods
~~~

The `src/news2market/` folder is the application's **source code**, **not a duplicate repository**. `requirements.txt` installs it for the unchanged `python -m news2market` command.

**Data rights:** third-party LM vocabulary, market data and article bodies are not redistributed. No source-code reuse license is presently granted.
