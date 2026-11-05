# Changelog

## v3.1.1 — GitHub release: preflight and research transparency

- Preserve the v3.1 three-company English dashboard (NVDA, AAPL, GOOGL) and Nasdaq-only local CSV workflow.
- Check the official Loughran–McDonald dictionary before price/news retrieval. Reuse a validated copy from a sibling local project when available; otherwise show a clear English setup error and official download link. Never bundle third-party dictionary bytes.
- Display LM dictionary prerequisite status in the local dashboard.
- Expand README `Limitations and resource-constrained development` with hardware, licensing, news coverage, model-quality, methodology and future-scaling limitations. No performance promises.
- Preserve the initial NVIDIA v2 report, figure and research reproducibility notes.
- Move the historical price-source manifest to `docs/`; ignore locally updated runtime price manifest to avoid accidental commits.

## v3.1 — Nasdaq-only English dashboard

- Replace Yahoo as price provider with manually imported, source-verified Nasdaq historical CSV files.
- Keep optional per-ticker CSV auto-reuse from an existing local project.
- English local interface and a unified three-company research command.
