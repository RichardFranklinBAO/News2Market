"""One-command, auditable News + SEC + LM + stock/QQQ workflow.

Usage (from repository root):
    python run_all.py --ticker NVDA

Requires official local LM dictionary and an identified SEC User-Agent.
Uses yfinance adjusted historical closes when available; verified existing
Nasdaq raw Close/Last CSVs are an explicitly labeled fallback.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from news2market import core
from news2market.research import cli as research_cli
from news2market.research.integration import run_market_integration
from news2market.research.sec import valid_agent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _price_rows_from_yahoo(ticker: str, start: date, end: date, folder: Path):
    """Fetch independently identified, adjusted CLOSE series (never raw Nasdaq)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError("yfinance is missing: install requirements.txt") from e
    output = {}
    hashes = {}
    files = {}
    for symbol in (ticker, "QQQ"):
        # Yahoo's end argument is exclusive. End at UTC today+1 inclusive.
        df = yf.download(symbol, start=start.isoformat(),
                         end=(end + timedelta(days=1)).isoformat(),
                         interval="1d", auto_adjust=True, actions=False,
                         progress=False, threads=False, timeout=20)
        if df is None or df.empty:
            raise RuntimeError(f"Yahoo returned no daily history for {symbol}")
        if "Close" not in df:
            raise RuntimeError(f"Yahoo response missing adjusted Close for {symbol}")
        series = df["Close"]
        # Versions differ in whether the columns are MultiIndex.
        if getattr(series, "ndim", 1) == 2:
            if symbol in series.columns:
                series = series[symbol]
            elif len(series.columns) == 1:
                series = series.iloc[:, 0]
            else:
                raise RuntimeError(f"Ambiguous Yahoo Close series for {symbol}")
        values = {}
        for index, value in series.items():
            day = index.date().isoformat() if hasattr(index, "date") else str(index)[:10]
            num = float(value)
            if not (num > 0 and num < float("inf")):
                continue
            if day in values:
                raise ValueError("Duplicate Yahoo price session: " + day)
            values[day] = num
        if len(values) < 3:
            raise RuntimeError(f"Too few valid Yahoo sessions for {symbol}")
        output[symbol] = values
        folder.mkdir(parents=True, exist_ok=True)
        csv_path = folder / (symbol + "_yahoo_adjusted.csv")
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "AdjustedClose"])
            for day, value in sorted(values.items()):
                writer.writerow([day, format(value, ".12g")])
        hashes[symbol] = _sha(csv_path)
        files[symbol] = str(csv_path)
    overlap = sorted(set(output[ticker]) & set(output["QQQ"]))
    if len(overlap) < 3:
        raise RuntimeError("No adequate overlapping Yahoo price sessions")
    if (end - date.fromisoformat(overlap[-1])).days > 10:
        raise RuntimeError("Yahoo history is too stale (>10 calendar days); no fresh market outcomes")
    rows = [{"date": day, f"{ticker}_close": output[ticker][day],
             "QQQ_close": output["QQQ"][day]} for day in overlap]
    audit = {
        "provider": "yahoo_via_unofficial_yfinance", "ticker": ticker,
        "benchmark": "QQQ", "price_basis": "yfinance auto_adjust=True, adjusted daily Close",
        "first_date": overlap[0], "last_date": overlap[-1],
        "matched_sessions": len(overlap), "files": files, "sha256": hashes,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Yahoo Finance access via yfinance is unofficial and may be unavailable",
            "Adjusted closes are not identical to raw Nasdaq Close/Last",
            "QQQ includes the analyzed company; not market-neutral alpha",
        ],
    }
    return rows, audit


def _price_rows_from_nasdaq(ticker: str):
    """Only use previously user-confirmed and hash-verified Nasdaq inputs."""
    for sym in (ticker, "QQQ"):
        if sym in core.NAS_PRICE_LINKS:
            core._reuse_previous_project_csv(sym, log=lambda _: None)
        path = core.INPUTS / "prices" / (sym + ".csv")
        if not path.is_file() or not core._nasdaq_evidence(sym, path):
            raise RuntimeError(
                f"Missing verified local Nasdaq file for {sym}: "
                "import via --stock-csv and --qqq-csv with --confirm-nasdaq")
    asset, _ = core._read_price_csv(core.INPUTS / "prices" / (ticker + ".csv"), ticker)
    qqq, _ = core._read_price_csv(core.INPUTS / "prices" / "QQQ.csv", "QQQ")
    overlap = sorted(set(asset) & set(qqq))
    if len(overlap) < 3:
        raise RuntimeError("Fewer than 3 overlapping verified Nasdaq price sessions")
    rows = [{"date": day, f"{ticker}_close": asset[day], "QQQ_close": qqq[day]}
            for day in overlap]
    audit = {
        "provider": "nasdaq_user_verified_local", "price_basis": "Nasdaq raw Close/Last, not dividend-adjusted",
        "ticker": ticker, "benchmark": "QQQ",
        "first_date": overlap[0], "last_date": overlap[-1],
        "matched_sessions": len(overlap),
        "sha256": {sym: _sha(core.INPUTS / "prices" / (sym + ".csv"))
                   for sym in (ticker, "QQQ")},
        "limitations": ["Manually imported data may end before recent event dates"],
    }
    return rows, audit


def import_nasdaq_pair(ticker: str, stock_csv: Path, qqq_csv: Path,
                       *, confirmed_nasdaq=False):
    """One-time explicit ticker attribution and safe local import of Nasdaq CSV pair.

    Nasdaq export has no built-in symbol field, so user must attest file origin.
    Both files are validated before either destination is changed.
    """
    if not confirmed_nasdaq:
        raise ValueError("Use --confirm-nasdaq only for genuine Nasdaq downloaded price files")
    from news2market.research.symbol_registry import canonical_symbol
    ticker = canonical_symbol(ticker)
    originals = {ticker: Path(stock_csv), "QQQ": Path(qqq_csv)}
    validated = {}
    for sym, src in originals.items():
        if not src.is_file() or src.stat().st_size > 5_000_000:
            raise ValueError(f"Missing or oversized Nasdaq CSV for {sym}: {src}")
        # Enforce genuine Nasdaq Date,Close/Last format; no synthetic substitution.
        raw = src.read_bytes()
        text = raw.decode("utf-8-sig")
        import io
        header = next(csv.reader(io.StringIO(text)), [])
        normalized = {"".join(c for c in str(x).lower() if c.isalnum())
                      for x in header}
        if not {"date", "closelast"}.issubset(normalized):
            raise ValueError(f"{src.name}: require Nasdaq Date and Close/Last columns")
        core.scripts_on_path()
        from nasdaq_csv_parser import parse_price_csv
        rows, basis = parse_price_csv(src)
        if len(rows) < 3 or basis != "raw_close_unadjusted":
            raise ValueError(f"{src.name}: invalid Nasdaq raw close export")
        validated[sym] = {"raw": raw, "rows": rows,
                          "sha256": hashlib.sha256(raw).hexdigest()}
    folder = core.INPUTS / "prices"
    folder.mkdir(parents=True, exist_ok=True)
    # This is a user-attested origin, never an independently provider-signed file.
    manifest = core._nasdaq_manifest()
    for sym, meta in validated.items():
        target = folder / (sym + ".csv")
        temp = folder / ("." + sym + ".tmp")
        temp.write_bytes(meta["raw"])
        os.replace(temp, target)
        manifest[sym] = {
            "source": "User-attested Nasdaq historical CSV import",
            "sha256": meta["sha256"], "rows": len(meta["rows"]),
            "first_date": meta["rows"][0]["date"],
            "last_date": meta["rows"][-1]["date"],
            "price_semantics": "Nasdaq raw Close/Last, not dividend-adjusted",
            "ticker_identity": "User-specified file-to-ticker attribution",
            "imported_utc": datetime.now(timezone.utc).isoformat(),
        }
    tmp = folder / ".SOURCE_MANIFEST.tmp"
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, folder / "SOURCE_MANIFEST.json")
    return {sym: {"rows": len(v["rows"]), "sha256": v["sha256"]}
            for sym, v in validated.items()}


def _prices(ticker: str, start: date, end: date, folder: Path, mode: str, log=print):
    errors = []
    if mode in ("auto", "yahoo"):
        try:
            result = _price_rows_from_yahoo(ticker, start, end, folder)
            log("Prices: fetched adjusted daily Yahoo historical closes")
            return result
        except Exception as exc:
            errors.append("Yahoo: " + str(exc)[:250])
            log("Yahoo prices unavailable: " + str(exc)[:180])
            if mode == "yahoo":
                raise
    if mode in ("auto", "nasdaq"):
        try:
            rows, audit = _price_rows_from_nasdaq(ticker)
            if errors:
                audit["failed_yahoo_attempt"] = errors
            log("Prices: using existing user-verified Nasdaq raw CSV pair")
            return rows, audit
        except Exception as exc:
            errors.append("Nasdaq: " + str(exc)[:250])
    raise RuntimeError("No usable source-verified price pair: " + "; ".join(errors))


def _news_rows(ticker: str, start: date, end: date, max_news: int, log=print):
    profile = core.COMPANIES[ticker]
    candidates, audit = core.discover_news(
        profile, ticker, start.isoformat(), end.isoformat(),
        max_news, use_proxy=False, log=log)
    cleaned = []
    seen = set()
    for row in candidates:
        if str(row.get("synthetic", "")).lower() in ("true", "1"):
            continue
        if row.get("company") not in (profile["name"], ticker, "NVIDIA CORPORATION"):
            continue
        if not str(row.get("url", "")).startswith("https://"):
            continue
        if len(str(row.get("text") or "")) < 100:
            continue
        day = str(row.get("published_date") or "")[:10]
        if not start.isoformat() <= day <= end.isoformat():
            continue
        url = str(row.get("url")).lower().rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        record = dict(row)
        record["ticker"] = ticker
        if not record.get("article_id"):
            record["article_id"] = "NEWS-" + hashlib.sha256(url.encode()).hexdigest()[:16]
        cleaned.append(record)
    return cleaned, audit


def run(ticker="NVDA", start=None, end=None, news_days=90,
        max_news=15, max_filings=50, prices="auto", agent=None,
        output_root=None, log=print, stock_csv=None, qqq_csv=None,
        confirm_nasdaq=False):
    ticker = ticker.upper()
    from news2market.research.symbol_registry import canonical_symbol, resolve_stock
    from news2market.research.identity import register_issuer
    ticker = canonical_symbol(ticker)
    end = date.fromisoformat(end) if isinstance(end, str) else (end or datetime.now(timezone.utc).date())
    if start:
        start = date.fromisoformat(start) if isinstance(start, str) else start
    else:
        start = end - timedelta(days=news_days)
    if start > end:
        raise ValueError("Start date must not exceed end date")
    if not 1 <= max_news <= 500:
        raise ValueError("max_news must be 1..500")
    if not 1 <= max_filings <= 100:
        raise ValueError("max_filings must be 1..100")
    agent = agent or os.environ.get("N2M_SEC_USER_AGENT", "")
    if not valid_agent(agent):
        raise ValueError("Set N2M_SEC_USER_AGENT to your real name and contact email before running")
    core.ensure_lm_dictionary(log=log)
    # Exact current listing/CIK check precedes any text or price collection.
    registry = resolve_stock(ticker, agent, core.INPUTS / "cache" / "symbol_registry")
    if ticker not in core.COMPANIES:
        core.COMPANIES[ticker] = {
            "name": registry["name"], "label": registry["name"],
            "query": registry["query"], "aliases": registry["aliases"],
            "official_feed": None, "official_host": "",
            "cik": registry["cik"], "has_issuer_scraper": False,
        }
    register_issuer({**registry, "official_host":
                     core.COMPANIES[ticker].get("official_host", "")})
    if bool(stock_csv) != bool(qqq_csv):
        raise ValueError("--stock-csv and --qqq-csv must be supplied together")
    if stock_csv:
        import_nasdaq_pair(ticker, Path(stock_csv), Path(qqq_csv),
                           confirmed_nasdaq=confirm_nasdaq)
    out_root = Path(output_root) if output_root else core.RESULTS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = out_root / ticker / "Unified" / stamp
    folder.mkdir(parents=True, exist_ok=False)
    audit = {
        "ticker": ticker, "status": "running",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "folder": str(folder), "stages": {}, "issuer_registry": registry,
        "limitations": [
            "Historical RSS/news discovery may not provide full backfill",
            "SEC recent submissions are not a complete historical filing archive",
            "SEC exhibits and first public market availability are not fully verified",
            "Market analysis is exploratory, not a validated Buy/Sell signal",
        ],
    }
    _write_json(folder / "unified_audit.json", audit)
    try:
        log("Stage 1/4: collecting source-identified News")
        articles, news_audit = _news_rows(ticker, start, end, max_news, log=log)
        news_csv = folder / "news_articles.csv"
        research_cli.write_rows(news_csv, articles, fields=[
            "article_id", "ticker", "company", "source", "source_type", "title",
            "url", "published_date", "published_time_quality", "text", "text_chars",
            "retrieved_utc", "synthetic", "extraction_strategy", "extraction_paragraphs",
        ])
        _write_json(folder / "news_collection_audit.json", news_audit)
        audit["stages"]["news"] = {"records": len(articles), "csv": str(news_csv),
                                   "sha256": _sha(news_csv)}
        log(f"News: {len(articles)} eligible collected bodies")

        log("Stage 2/4: collecting SEC EDGAR and remeasuring combined corpus")
        sec_args = SimpleNamespace(
            ticker=ticker, start=start.isoformat(), end=end.isoformat(),
            max_filings=max_filings, fetch_bodies=True, sec_user_agent=agent,
            submissions_json=None, news_csv=str(news_csv) if articles else None,
            dictionary=research_cli.LM_PATH, no_tfidf=False,
            output_root=folder / "stages",
        )
        sec_folder, sec_audit = research_cli.command_sec(sec_args)
        features_path = sec_folder / "research_features.csv"
        if not features_path.is_file():
            raise RuntimeError("No complete SEC/news text for LM measurement; see SEC data-quality audit")
        audit["stages"]["sec_and_lm"] = {
            "filings": sec_audit["disclosures_selected"],
            "eligible_scored": sec_audit["research_scores"]["text_scored_records"],
            "features_csv": str(features_path), "sha256": _sha(features_path),
            "quality_report": str(sec_folder / "sec_data_quality_report.md"),
        }
        log(f"SEC: {sec_audit['disclosures_selected']} filings selected")

        log("Stage 3/4: loading stock and QQQ market prices")
        price_start = min(start, end - timedelta(days=365 * 5 + 5))
        effective_price_mode = "nasdaq" if stock_csv else prices
        price_rows, price_audit = _prices(
            ticker, price_start, end, folder / "prices",
            effective_price_mode, log=log)
        _write_json(folder / "price_audit.json", price_audit)
        audit["stages"]["prices"] = {
            "provider": price_audit["provider"], "matched_sessions": len(price_rows),
            "first_date": price_audit["first_date"], "last_date": price_audit["last_date"],
        }

        log("Stage 4/4: aligning and validating News + SEC signals vs QQQ")
        market_folder = folder / "market"
        market_audit = run_market_integration(
            ticker, features_path, market_folder,
            price_rows=price_rows, price_provenance=price_audit)
        audit["stages"]["market"] = {
            "aligned_events": market_audit["aligned_events"],
            "source_groups": market_audit["source_groups"],
            "predictive_validation": market_audit["predictive_validation"],
        }
        audit["status"] = "complete_with_limitations"
        log("COMPLETE. All results: " + str(folder))
    except Exception as exc:
        audit["status"] = "failed_or_partial"
        audit["error"] = type(exc).__name__ + ": " + str(exc)[:450]
        log("STOPPED; partial auditable outputs saved: " + audit["error"])
        raise
    finally:
        _write_json(folder / "unified_audit.json", audit)
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-command News + SEC + LM + QQQ research")
    parser.add_argument("--ticker", default=None, help="US stock symbol e.g. NVDA, MSFT, AMD, TSLA")
    parser.add_argument("--interactive", action="store_true", help="Prompt for a US stock ticker in Terminal")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD; default end minus news-days")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD inclusive; default today UTC")
    parser.add_argument("--news-days", type=int, default=90)
    parser.add_argument("--max-news", type=int, default=15)
    parser.add_argument("--max-filings", type=int, default=50)
    parser.add_argument("--prices", choices=["auto", "yahoo", "nasdaq"], default="auto")
    parser.add_argument("--stock-csv", type=Path, help="User-downloaded Nasdaq company historical CSV")
    parser.add_argument("--qqq-csv", type=Path, help="User-downloaded Nasdaq QQQ historical CSV")
    parser.add_argument("--confirm-nasdaq", action="store_true",
                        help="Attest both selected CSV files came from Nasdaq historical downloads")
    parser.add_argument("--sec-user-agent", default=None, help="Real name and contact email")
    parser.add_argument("--output-root", default=None, type=Path)
    args = parser.parse_args(argv)
    if args.interactive or (args.ticker is None):
        import sys
        if not sys.stdin.isatty():
            parser.error("Provide --ticker for non-interactive execution")
        print("News2Market — US Stock Research")
        print("Enter a real US stock ticker (examples: NVDA, AAPL, MSFT, AMD, TSLA)")
        args.ticker = input("Stock ticker: ").strip().upper()
    result = run(ticker=args.ticker, start=args.start, end=args.end,
                 news_days=args.news_days, max_news=args.max_news,
                 max_filings=args.max_filings, prices=args.prices,
                 agent=args.sec_user_agent, output_root=args.output_root,
                 stock_csv=args.stock_csv, qqq_csv=args.qqq_csv,
                 confirm_nasdaq=args.confirm_nasdaq)
    print(json.dumps({
        "status": result["status"], "run_folder": result["folder"],
        "news": result["stages"].get("news", {}).get("records"),
        "sec": result["stages"].get("sec_and_lm", {}).get("filings"),
        "market": result["stages"].get("market", {}),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
