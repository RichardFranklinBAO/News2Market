# News2Market — stage-organized helper scripts

**Run the full project from the repository root using `python run_all.py`.**
The stage files are internal helpers, not alternative end-to-end entrypoints.
`src/news2market/` contains the orchestrator, financial research integration,
source verification, SEC acquisition, and market-validation logic. No real
market data or LM dictionary files are redistributed.

| Order | Folder | What it does |
|---|---|---|
| 1 | [step_01_collect](step_01_collect/) | Discover news, retrieve publisher full text, optionally collect NVIDIA issuer releases |
| 2 | [step_02_prepare](step_02_prepare/) | Clean narrative/boilerplate and prepare text without overwriting original evidence |
| 3 | [step_03_nlp](step_03_nlp/) | Load official LM dictionary, score sentiment, create tentative event tags, optional local LLM checks |
| 4 | [step_04_market](step_04_market/) | Parse validated Nasdaq price CSV and construct daily stock-vs-QQQ return outcomes |
| 5 | [step_05_report](step_05_report/) | Compare original versus cleaned text scoring as a sensitivity diagnostic |
| — | [shared](shared/) | Common configuration, paths, CSV/JSON helpers |

**Important:** The unified runner performs a modern News + SEC + LM + market
alignment pipeline via `src/news2market/research/`; some stage files remain
available to support the earlier News-only dashboard and local experiments.
Stage order describes the operations, not a claim that every optional helper is
executed for every ticker.

Commands:

```bash
python -m pip install -r requirements.txt
python run_all.py --help
python run_all.py --ticker AMD
python -m unittest discover -s tests -v
```

Research caveat: data access can fail or be incomplete. Missing/news-empty and
insufficient-evidence results are documented limitations, not passing forecasts.
