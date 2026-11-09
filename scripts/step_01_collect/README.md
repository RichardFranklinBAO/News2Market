# Step 1 — Collect source documents

- `news_feed_discovery.py`: discover candidate financial articles from RSS and publisher feeds and audit access/coverage.
- `external_article_fetcher.py`: retrieve qualified original full text and extraction evidence; do not treat RSS snippets as full bodies.
- `nvidia_scraper.py`: optional NVIDIA first-party release collection for the legacy issuer-news workflow.

SEC filing collection and issuer/CIK verification are in `src/news2market/research/sec.py` and `symbol_registry.py`; they are called automatically by root `run_all.py`.
