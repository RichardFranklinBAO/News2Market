# Financial Text Research Extension

This is an **optional research workflow** within News2Market. The original **three-company English dashboard** remains available using `python -m news2market --web`. Nothing here establishes that financial text predicts stock returns.

## Research question

How do different text representations characterize firm-level economic information in corporate disclosures and news, and what additional validation is required before using those representations in empirical asset-pricing research?

The extension adds **SEC EDGAR disclosure provenance and local text measurement** rather than pretending to provide a validated earnings-surprise signal or reproduce a published transformer method.

## Provenance and research inputs

- **SEC EDGAR Submissions API:** https://www.sec.gov/search-filings/edgar-application-programming-interfaces. The program reads the public `data.sec.gov/submissions/CIK##########.json` submission JSON for **NVDA, AAPL, and GOOGL**, using the same company CIK registry as the main application. The optional primary HTML document stage uses the filing's accession number and official filename. It does **not** retrieve every attachment or all historical submission shards. The filings selected are **8-K, 10-Q, and 10-K**; annual and quarterly reports are not homogeneous with 8-Ks or independent news.
- **Fair-access rules:** https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data. Identify yourself in `N2M_SEC_USER_AGENT` with a **real name/contact email**, make a small number of slow requests, and stop on 403/429. Do not bypass access restrictions. No SEC authentication key is needed for the submissions JSON API.
- **LM dictionary:** https://sraf.nd.edu/loughranmcdonald-master-dictionary/. The exact official `Loughran-McDonald_MasterDictionary_1993-2025.csv` must be placed in `Inputs/`; the repository does **not** redistribute it.
- **Methods literature:** Rizinski et al., *Sentiment Analysis in Finance: From Transformers Back to eXplainable Lexicons (XLex)*, IEEE Access (2024), https://doi.org/10.1109/ACCESS.2024.3349970. The provided reference implementation is under **Apache 2.0**; the existing XLex research uses RoBERTa and SHAP to construct a new lexicon. This extension does **not** train XLex, download its learned vocabulary, or reproduce any reported accuracy improvement.
- **Other user-provided resources:** FinMTEB (finance embedding benchmark), FinDKG (dynamic knowledge graphs), and FinReflectKG. These inform *future benchmarking ideas* but **are not code dependencies or implemented results** in this release. The supplied general financial-data guide covers several unrelated data services (e.g. Yahoo Financials, NewsAPI, DBnomics and Twitter); no proprietary keys or copied tutorial source code are required here.

## Quick Start: research commands

From the GitHub repository root, after installing `requirements.txt`, run:

```bash
# Original interactive application (unchanged)
python -m news2market --web

# Inspect the new research mode
python -m news2market research --help

# SEC company filing metadata (without downloading any filing bodies)
# Replace with your REAL contact details; do not use the placeholder literally.
export N2M_SEC_USER_AGENT='Your Name your-real-email@example.com'
python -m news2market research sec \
  --ticker NVDA --start 2025-01-01 --end 2026-11-05 --max-filings 10

# Optional: request permitted primary HTML filing text and compute LM + descriptive TF-IDF
python -m news2market research sec \
  --ticker NVDA --start 2025-01-01 --end 2026-11-05 \
  --max-filings 5 --fetch-bodies

# Re-score an EXISTING local article-level CSV (no network required)
python -m news2market research measure \
  --ticker AAPL --input-csv path/to/local_articles.csv
```

### Input/output format

Saved article CSVs should have at least `article_id,title,text,published_date,source,url`. A `body` or `full_text` field can substitute for `text`. The optional `sec --news-csv` argument combines an existing local news collection with metadata/disclosures of the **same selected ticker**; the program does not establish ticker identity for a file merely because a user has named it accordingly.

All outputs are local, timestamped and ignored by Git:

```text
Results/<TICKER>/Research/<UTC_RUN_ID>/
    sec_filings.csv          # Filings metadata, accession and source URL (SEC mode)
    corpus_local.csv         # Source text and provenance for local analysis (if text exists)
    research_features.csv    # LM Positive/Negative/Uncertainty rates and polarity
    tfidf_top_terms.csv      # Descriptive, untrained top TF-IDF terms per document
    research_audit.json      # Collection status, hashes, omissions and caveats
```

Missing filings or unsupported documents are recorded instead of replaced with synthetic content. Raw source text in `corpus_local.csv` is **not included in GitHub**. The original News2Market `Results/` folders are untouched.

## Metrics and methodological integrity

For each document with dictionary-tokenized word count `W`, LM Positive `P`, Negative `N` and Uncertainty `U` counts:

- `LM Positive rate = 1000 × P / W`; `Negative rate = 1000 × N / W`; `Uncertainty rate = 1000 × U / W`.
- An alternative polarity index `(P−N)/(P+N)` is reported **only** when `P+N>0`. A zero-hit article is **missing**, not neutral economic information.
- LM is a domain vocabulary, not an independently validated measurement of *unexpected* company fundamentals. Text length and disclosures' legal boilerplate can change frequencies.
- TF-IDF is **an unsupervised representation**, *not* a sentiment classifier and *not* XLex. Its `tfidf_top_terms.csv` is a corpus-specific descriptive result, not sample-out-of-time validation.

### Optional evaluation when independently verified labels exist

A user may supply a CSV with `article_id,label,label_source`, where `label` is `negative`, `neutral`, or `positive`, and `label_source` must assert `human_verified` or `independent_manual`. Use:

```bash
python -m news2market research benchmark \
  --ticker NVDA \
  --corpus-csv path/to/corpus_local.csv \
  --labels-csv path/to/independent_human_labels.csv
```

The code rejects **AI-assisted pseudo-ground-truth** and tiny or non-diverse labeled corpora. When there are enough distinct dates and independently annotated documents, it evaluates a **train-only fitted TF-IDF + logistic regression** classifier on a later-date holdout, plus the project's heuristic LM polarity class. It reports coverage, macro F1, balanced accuracy and held-out sample size. **The program cannot independently verify whether labels claiming to be human-reviewed actually were.** This compares *text labels*, **not** abnormal returns, and there is no proven research finding without independently collected data.

### Why a stock-return model is not claimed here

A date listed by the SEC, RSS or a publisher is not necessarily the first instant a trading participant could see the information. Filing text can mix legal boilerplate with material news; the SEC primary document may omit economically relevant exhibits. The original pilot had too few independent signal days for credible high-dimensional out-of-sample modeling. A valid market-return extension needs a longer **as-of-timestamped** panel, baselines (e.g. lagged returns, volatility, firm characteristics), walk-forward splits, multiple-testing controls and pre-specified diagnostics. These remain **research work**, not implemented evidence.

## Limitations / future additions

- SEC Submissions `filings.recent` does not automatically cover a complete historic archive; use its referenced older shards or bulk data with separately audited provenance for long backfills.
- SEC HTML retrieval can be denied, rate-limited, partial or dominated by tables/boilerplate. The prototype caps each response and records truncation. It is not a robust section-level 10-K parser.
- News, disclosures and 10-Q/10-K documents have different lengths, timing conventions and editorial processes; pooling raw scores can introduce measurement bias.
- Larger LLMs, **OpenAI API** comparisons, XLex lexicon reproduction, FinMTEB evaluations, dynamic knowledge graphs and large-scale multi-stock panel studies are **possible future work**, not implemented features.
- This extension is intentionally lightweight enough for personal-computer development. Robust U.S.-market-wide scaling would also require licensed, consistently timestamped data and comprehensive entity resolution, not just more RAM.
