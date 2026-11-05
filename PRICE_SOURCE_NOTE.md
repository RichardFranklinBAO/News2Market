# Market-price source audit: Nasdaq only

**v2 original pilot:** User-downloaded Nasdaq `NVDA` and `QQQ` daily `Close/Last` CSVs spanning 2021-11-05 to 2026-11-04, 1,254 date-matched trading sessions.

**v3.1:** Yahoo and yfinance have been fully removed. A user chooses a stock and the project reuses locally verified Nasdaq files or accepts a one-time user-confirmed manual Nasdaq CSV import. Files are kept in `Inputs/prices/` with SHA-256 checksums and provenance under `Inputs/prices/SOURCE_MANIFEST.json`. Previously verified files in an adjacent `News2Market` project are copied when both original manifest and file hashes agree. Existing raw data in the original project is never changed.

**Scope:** A free, unauthorized Nasdaq website scraper is intentionally not provided. Nasdaq's published terms restrict automated extraction; manual/other use remains subject to terms and permissions. The official historical-data pages are linked from the dashboard. A separately licensed Nasdaq API connector could be added later if the owner receives proper authorization.

**Prices:** Nasdaq `Close/Last` is not cash-dividend-adjusted total return. Preserve any stock split methodology and choose consistent input sources for both ticker and QQQ. The program refuses unverified, non-Nasdaq local files rather than silently mixing providers.
