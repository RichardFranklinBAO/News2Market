# News2Market

**Company-aware financial news collection, auditable NLP measures, and exploratory empirical research.**

News2Market is an independent Python research prototype. It collects company-related news and SEC disclosures, converts unstructured text into documented financial variables, checks data quality, and explores links with market outcomes. The current implementation supports **NVIDIA (NVDA), Apple (AAPL), and Alphabet (GOOGL)** through one configurable workflow; broader U.S. equity coverage is a future direction.

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

## Quick Start

**Choose one of two independent workflows** (both use the official LM dictionary):

| Workflow | Purpose | Additional input | Start |
|---|---|---|---|
| **News + Market Report** | Scrape firm news and explore LM text scores alongside stock/QQQ price returns | Manually imported Nasdaq stock and QQQ CSVs | `python -m news2market --web` |
| **SEC Collection + LM Analysis** | Retrieve and audit 8-K/10-Q/10-K primary documents, then score complete bodies | Genuine SEC User-Agent; **no Nasdaq CSV required** | `python -m news2market research sec ... --fetch-bodies` |

**[Detailed Mac walkthrough for both workflows](docs/TWO_WORKFLOWS.md)** — including exact commands, result locations, and what constitutes a successful check.

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
- **For market analysis:** download the selected company's and **QQQ** daily price CSVs from [Nasdaq](https://www.nasdaq.com/market-activity) and import both using the English dashboard. Automatic Nasdaq downloads are **not** supported. The SEC-only workflow does **not** need stock prices.
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
