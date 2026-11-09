# Step 4 — Market price and outcome handling

- `nasdaq_csv_parser.py`: validate downloaded historical price files and parse daily data.
- `signal_core.py`: legacy news-only signal-session aggregation and descriptive return construction.

The current unified market study aligns News/SEC features and stock-minus-QQQ 1/3/5-session price returns in `src/news2market/research/integration.py`; its provisional holdout is in `validation.py`. Yahoo and Nasdaq price source provenance is recorded by `run_all.py` and its price helpers.
