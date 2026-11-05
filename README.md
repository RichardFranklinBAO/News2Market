# News2Market v3.1.1

**Nasdaq-only historical-data import · Three-company news research · 100% English local dashboard**

**Company-aware web scraping and financial-text dataset construction across three U.S.-listed firms.** Select NVIDIA (NVDA), Apple (AAPL), or Alphabet Class A / Google (GOOGL) in the English dashboard. A **single shared Python pipeline** dynamically selects the corresponding issuer source and company-specific news query, discovers third-party coverage, extracts permitted text, constructs an auditable firm-level news dataset, applies Loughran–McDonald (LM) financial text measures, and optionally runs local Ollama/Qwen2.5 1.5B labeling and exploratory QQQ-relative return analysis. **No separate per-company analysis scripts or manually entered article URLs are required.** This is a three-firm research prototype, not an all-U.S.-equity crawler.

## Research motivation and predoc-relevant skills

**Research question.** Can publicly available corporate announcements and third-party reporting be converted into **traceable, firm-specific economic text measures**, and how should those measures be validated before they are linked to financial-market outcomes? The emphasis is on **building the dataset, defining the measurement, and testing its limitations**—not claiming to predict stock prices.

This project provides concrete examples of research-assistant tasks commonly required in empirical economics and finance:

| Research skill | Evidence in this repository |
|---|---|
| **Company-aware web scraping and non-traditional data collection** | Develops a configurable pipeline to discover, retrieve, and structure news relevant to a selected U.S.-listed company. The architecture is designed for future expansion across the broader U.S. equity market; given the computing and data-access constraints of this independently developed project, the current proof of concept focuses on three firms: **NVIDIA (NVDA), Apple (AAPL), and Alphabet (GOOGL)**. The pipeline records source provenance, filters company-relevant articles, extracts permitted full text, and audits retrieval failures. |
| **Constructing firm-specific research datasets and data parsing** | Converts unstructured company-specific issuer HTML/RSS and independent publisher pages into consistently structured, **ticker-labeled article-level datasets**; normalizes links, deduplicates and audits sources, and joins eligible text measures with the **selected firm's** Nasdaq historical CSV and QQQ benchmark. Each ticker has its own run directory and provenance files. |
| **Python-based NLP and AI-assisted measurement** | Implements Loughran–McDonald financial word counts, per-1,000-word positive/negative/uncertainty frequencies, and a secondary polarity index. Optionally uses **local Ollama/Qwen2.5 1.5B** for structured event and economic-channel annotations with JSON/evidence checks; these LLM labels are **not validated ground truth**. |
| **Statistical analysis in Python** | Builds daily, date-aligned sentiment and return observations; computes correlations and exploratory OLS with HC1 standard errors; generates plots, coefficient estimates, and machine-readable analysis summaries with limitations. |
| **Research design, sensitivity checks, and diagnostics** | Compares original versus boilerplate-cleaned text; checks sparse dictionary matches, missing data and model-output failures; distinguishes issuer press releases from independent editorial sources. These are observational measurement and engineering evaluations, **not randomized experiments**. |
| **Communicating research results** | Documents methods, data sources, variable definitions, null findings and unresolved threats to validity in a reproducibility guide and [research report](docs/RESEARCH_REPORT.md), rather than treating technically successful code as proof of an economic effect. |

### Company-aware news crawling: one pipeline, three selectable stocks

The **same** function, `v3_core.discover_news()`, is called regardless of the chosen ticker. A compact `COMPANIES` registry provides the **issuer identity, ticker, news query, known aliases, official source and SEC CIK**; these are configuration values, **not three copies of the scraper**. The dashboard passes the selected ticker to `v3_core.run_pipeline()`, which uses the corresponding profile throughout collection, dataset creation and the analysis pipeline.

| Selected company | Configured first-party discovery | Additional independent discovery | Company-aware filtering |
|---|---|---|---|
| **NVIDIA — NVDA** | Dedicated NVIDIA Newsroom HTML collector | Public search/publisher RSS, including Google News search, TechCrunch, CNBC Tech and Ars Technica | NVIDIA, NVDA, GeForce, Blackwell and other profile aliases |
| **Apple — AAPL** | [Apple Newsroom RSS](https://www.apple.com/newsroom/rss-feed.rss) | The **same** search/publisher RSS sources, queried for Apple | Apple, AAPL, iPhone, iPad, MacBook and related aliases; excludes some obvious fruit-related false positives |
| **Alphabet / Google — GOOGL** | [Google Blog RSS](https://blog.google/rss/) (official company blog, **not** an issuer-press-release archive) | The **same** search/publisher RSS sources, queried for Google | Google, Alphabet, GOOGL, DeepMind, Google Cloud and related aliases |

**For each selected company:** query the configured available feeds → filter by query, date and company aliases → normalize URLs and remove duplicate candidates → attempt permitted full-text extraction → classify first-party vs. third-party sources → build and audit the firm's article records → compute LM financial-text features. Company-specific output is isolated under `Results/<TICKER>/V3/<run_id>/`. The selected firm's market-price CSV is paired with **QQQ** using a separate shared analysis stage; prices must first be obtained/imported from Nasdaq under the provider's terms.

**What the implementation does not yet establish:** RSS retrieval and source coverage depend on network access, site permissions and publisher layouts. Some filtering is heuristic and can miss articles or admit unrelated mentions. NVIDIA's separate HTML collector is currently unique to NVIDIA; the Apple and Google issuer sources use their configured RSS feeds. **Live news collection and downstream empirical outputs have not been independently validated for all three companies.** Three-stock offline tests demonstrate software routing, **not** complete real-world news coverage, comprehensive market-wide scraping, OCR, or verified economic validity.

### A concrete research workflow

1. **Acquire:** select NVDA/AAPL/GOOGL; dynamically query that company's configured issuer source and third-party RSS coverage, then preserve original links, ticker identity, source classification and timing caveats.
2. **Structure:** extract full text, identify duplicates and boilerplate, and build a documented **article-level research dataset**.
3. **Measure:** compute explainable financial-text variables, including word-frequency rates and an alternative polarity index; preserve original versus cleaned versions.
4. **Validate:** audit data quality and local-LLM outputs, construct dated stock/benchmark outcomes, and conduct **exploratory** statistical tests.
5. **Report:** publish the method, code, assumptions, reproducibility instructions, and negative findings alongside the outputs.

**Observed historical example (NVIDIA only):** 30 first-party announcements produced 18 dated sentiment-signal days; the exploratory NVDA-minus-QQQ regression showed no statistically significant association (HC1 `p ≈ 0.860`). The strength of this example is the auditable research workflow, **not** a positive predictive result. The v3 interface extends the *software design* to Apple and Alphabet; it does not establish three independently validated economic findings.

**Scope and non-claims.** The repository demonstrates **Python**, rather than claiming experience here with R, Stata or MATLAB. It uses **pretrained local-LLM inference**, not custom model training or fine-tuning. **OCR, large-scale historical database infrastructure, structural/dynamic economic modeling, randomized experiments and a comprehensive literature review are not implemented in this project.** The measurement design draws on the Loughran–McDonald financial-text literature, but independent economic validity must still be tested. These are potential extensions with additional research resources, not completed work.

## Quick start

```bash
# In a fresh GitHub clone of this repository:
python -m pip install -r requirements_v3.txt
python run_v3.py --web
```

**Before pressing Run:** the dashboard displays the required **official Loughran–McDonald dictionary** and Nasdaq stock/QQQ CSV status. The dictionary is **not included in GitHub**. The program first checks `Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv` and, if missing, tries to validate and reuse a local copy from a sibling `News2Market/Inputs/` directory. If neither exists, download the official version from [Notre Dame SRAF](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) and place it under `Inputs/`. The run stops **before any market/news requests** if the file is absent or invalid; it never uses a synthetic substitute.

The Nasdaq CSV files likewise remain local-only, can be imported through the English dashboard, and must include the selected stock **plus QQQ**. A new clone without these authorized research inputs will show installation prompts, not produce empirical results.

Open `http://127.0.0.1:8765`. The UI, status indicators, data import, charts, and explanations are entirely in English. More detailed setup is in [`V3_START_HERE.md`](V3_START_HERE.md).

## Market data — Nasdaq only (no Yahoo)

This release **does not use Yahoo Finance or yfinance**. It supports **locally preserved official Nasdaq historical CSV exports only**, with `Date` and `Close/Last` columns. When available, it automatically reuses source-hash-verified NVDA and QQQ CSVs from your existing sibling `News2Market` project. The web UI can import a user-confirmed Nasdaq CSV for any of the three companies and QQQ, then automatically reuse it for subsequent runs.

| Symbol | Issuer / fund | Official Nasdaq historical data |
|---|---|---|
| NVDA | NVIDIA Corporation | https://www.nasdaq.com/market-activity/stocks/nvda/historical |
| AAPL | Apple Inc. | https://www.nasdaq.com/market-activity/stocks/aapl/historical |
| GOOGL | Alphabet Inc., Class A | https://www.nasdaq.com/market-activity/stocks/googl/historical |
| QQQ | Invesco QQQ Trust ETF, benchmark | https://www.nasdaq.com/market-activity/etf/qqq/historical |

Original NVDA/QQQ pilot range: **2021-11-05 through 2026-11-04** (1,254 paired trading sessions, user-provided raw `Close/Last`). The three-company live program independently selects the latest 1, 3 or 5 years, subject to actual imported CSV coverage. Raw Nasdaq `Close/Last` is **not adjusted for cash dividends**; vendor/corporate-action handling must be verified. Results are not total returns or factor-adjusted abnormal returns.

**Why not automatically download from Nasdaq.com?** Nasdaq's site terms restrict unauthorized automated extraction for analysis. The free MVP therefore requires an authorized/user-permitted original download and a one-time local import. It does not evade rate limits or simulate a Nasdaq API connection. A licensed/explicitly permitted official API could later enable genuinely automated downloads; no claim is made that it exists in this release.

## Dataflow / technology stack

1. **Company identity:** fixed and audited profiles for NVDA, AAPL and GOOGL (including ticker, official source, CIK and search aliases).
2. **Historical prices:** verified local Nasdaq CSVs for the selected stock and QQQ; no cross-vendor mixing; dated joins and per-run provider audits.
3. **Company-aware news retrieval:** the selected NVDA/AAPL/GOOGL profile dynamically controls the issuer-specific HTML/RSS source, company name/aliases, date and keyword filtering, plus shared independent publisher feeds; canonical URL deduplication and respectful, restricted-access HTML requests.
4. **Text extraction and quality control:** bounded extraction; original evidence retained; page/RSS date audit; source-specific boilerplate controls.
5. **LM dictionary sentiment:** Notre Dame's Loughran–McDonald Master Dictionary (user-downloaded separately): token counts and per-1,000-word positive, negative, uncertainty rates. Project-defined polarity `(positive-negative)/(positive+negative)` is a *secondary, unvalidated index*; categorical thresholds are project heuristics, not established financial facts.
6. **Optional local model:** Ollama + Qwen2.5 1.5B, constrained structured output and evidence IDs. In the historical 30-NVIDIA-article pilot 9/30 passed structural/evidence checks, 3/30 needed review and 18/30 failed. These are not independent human accuracy statistics.
7. **Exploratory inference:** conservative date-only alignment, NVDA/AAPL/GOOGL price-return minus QQQ, Pearson correlation and HC1 OLS if enough dated news signals. No predictive, causal or trading-profit claim.
8. **Auditability:** isolated run directories under `Results/<ticker>/V3/<run_id>/`, input hashes, machine-readable audit JSON and per-article LM CSVs.

**Core software:** Python 3.11–3.12, requests, BeautifulSoup, trafilatura, pandas, NumPy, statsmodels, matplotlib and a local stdlib HTTP dashboard. No paid APIs, no Yahoo package or hosted interface.

## Source rights and research limitations

* The complete LM dictionary, news bodies and original market CSVs must be acquired by each research user under applicable terms; they are not bundled.
* A Nasdaq CSV download has **no ticker field**, so original ticker identity cannot be verified from its contents alone. The user must attest to the ticker and official origin when importing.
* RSS failures, legal access restrictions and missing/news-only metadata can mean zero extracted news. Never use synthetic fixtures as empirical data.
* Without verified intraday publication timestamps, same-day price reaction and causal event-study statements are unsupported.
* LM tone is distinct from market surprise: e.g. financial risk disclaimers and sparse sentiment hits can distort document-level polarity.
* Three-company live end-to-end internet acquisition has not been independently confirmed in the user environment. Offline tests are engineering checks, not financial validation.

## Limitations and resource-constrained development

This project was created **independently on a personal computer**, using freely accessible research tools rather than institutional computing clusters, licensed market-data feeds, a production news archive, or a team of human annotators. The three-company scope is an intentional, testable **proof of concept** for a research portfolio—not a claim of production readiness. These limitations explain the current **implementation scope**, but they do not make its reported statistical results or unvalidated labels more reliable.

| Current limitation | Why it matters | Potential direction with additional resources (not yet implemented) |
|---|---|---|
| **Local hardware and model scale** | Running Ollama `qwen2.5:1.5b` on a memory-constrained personal Mac limits context length, throughput and model choice. The historical 30-article audit produced 9 structurally valid/evidence-linked outputs, 3 review cases and 18 failures. | Benchmark stronger models with sufficient RAM/VRAM or authorized compute; use independent human judgments to test validity, not assume bigger models are automatically better. |
| **Dictionary installation / redistribution** | The official LM 1993–2025 Master Dictionary is **not committed to GitHub** and must be downloaded separately under Notre Dame's terms. A new clone without it cannot perform actual LM scoring. | Make local setup and integrity checks easier; use a source-authorized distribution or download mechanism only if the provider permits one. The app now checks the file **before** starting news collection. |
| **Market-price access** | This free version does not have licensed automated Nasdaq API access; it **does not** use Yahoo or bypass Nasdaq restrictions. NVDA/AAPL/GOOGL and QQQ require one-time user-supplied Nasdaq `Close/Last` files. | Add an explicitly licensed/authorized provider adapter, scheduled updates, adjusted-close/total-return treatment, and multi-vendor quality cross-checks. |
| **News coverage and entity matching** | Public RSS feeds can time out, change format or restrict access. Candidate relevance is largely lexical, source coverage differs by issuer, and the available sample is small. The original 30-article NVIDIA pilot does not imply five years of news. | Expand to verified and licensed archives, more issuers, broader historical coverage, and robust company/alias/entity resolution with manual audits. |
| **Information timing and empirical validity** | Most dates are day-level rather than verified first market-visible times. Relative `Close/Last` **price returns** against QQQ are not dividends-adjusted total returns or factor-adjusted abnormal returns. No causal or predictive interpretation is justified. | Acquire reliable publication timestamps, calibrate market calendars, implement factor adjustment, matched controls, out-of-sample evaluation and more defensible event-study designs. |
| **Lexicon measurement** | LM was developed for financial disclosures; earnings-call notices, legal disclaimers and sparse matched words can generate misleading extremes. The project's polarity formula and category thresholds are **design choices, not a validated economic surprise measure**. | Compare positive/negative/uncertainty frequencies per 1,000 words, alternative lexica, cleaned text and independently labeled data, then test sensitivity. |
| **Research software maturity** | The dashboard is **local-only**, processes one selected company per run and has not been security-hardened or load-tested for arbitrary public Internet deployment. | Add robust job queues, caching, monitoring, permissions, reproducible data manifests and CI; expand the company registry after testing, rather than claiming current all-US-market support. |

**Development outlook:** With additional computing capacity, properly licensed data access, more complete historical coverage and stronger independent validation, this architecture can be extended to a more comprehensive and rigorous financial-text research platform. These are **feasible development directions**, not achieved results or guaranteed predictive gains. Honest reporting of limitations, including negative or non-significant findings, is part of the research contribution.

## Research provenance and interpretation

* **Historical NVIDIA pilot (v2):** Original NVDA and QQQ Nasdaq CSVs covered **2021-11-05 through 2026-11-04**, yielding **1,254 paired trading sessions**. The 30 NVIDIA Newsroom observations produced **18 signal days** and **no significant linear return association** (HC1 p ≈ 0.8602); these results are historical v2 evidence, not a claim about AAPL or GOOGL.
* **Three-company interface (v3.1):** Uses a **rolling** price window of 1/3/5 years and news window of 14/30/60/90 days. Exact effective coverage depends on provided Nasdaq CSVs and legitimately accessible news at run time. Each run records its own file hashes and actual data availability.
* **Official sources:** [Nasdaq NVDA](https://www.nasdaq.com/market-activity/stocks/nvda/historical), [Nasdaq AAPL](https://www.nasdaq.com/market-activity/stocks/aapl/historical), [Nasdaq GOOGL](https://www.nasdaq.com/market-activity/stocks/googl/historical), [Nasdaq QQQ](https://www.nasdaq.com/market-activity/etf/qqq/historical), [Notre Dame LM Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/), [NVIDIA Newsroom](https://nvidianews.nvidia.com/). See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) and [`docs/RESEARCH_REPORT.md`](docs/RESEARCH_REPORT.md).
* The live v3 workflow has been tested offline using synthetic test fixtures and the original real Nasdaq files for data parsing. **A live online end-to-end test of all three firms, including full news coverage and market inference, remains incomplete.** Synthetic fixtures are never described as real market evidence.

## Testing and command line

```bash
python -m unittest discover -s tests -v
python run_v3.py --ticker AAPL --news-days 30 --price-years 5
```

The second command requires the official LM dictionary and verified local Nasdaq CSVs for **AAPL and QQQ**. It may return zero articles or an explicit access error when upstream providers are unavailable. Unit tests with synthetic fixtures validate engineering behavior but are not evidence about real equity returns.

The CLI and web app share `v3_core.run_pipeline`. Select `--price-mode auto` (default, verified local Nasdaq auto-reuse) or `--price-mode nasdaq_csv` (only files in this project's Inputs). Neither mode makes unauthorized Nasdaq requests. See [`V3_START_HERE.md`](V3_START_HERE.md) and [`PRICE_SOURCE_NOTE.md`](PRICE_SOURCE_NOTE.md).

**Research status:** exploratory prototype; no validated stock return forecasting or reliable LLM label accuracy. The initial NVDA pilot (v2) obtained 18 signal days and no statistically significant association (HC1 p ≈ 0.8602). The new three-stock live output remains to be individually verified.
