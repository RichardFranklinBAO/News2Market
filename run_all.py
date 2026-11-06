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
        core._reuse_previous_project_csv(sym, log=lambda _: None)
    state = core.price_status(ticker)
    if not state["ready"]:
        raise RuntimeError("Verified local Nasdaq stock and QQQ CSVs are not both ready")
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
        output_root=None, log=print):
    ticker = ticker.upper()
    if ticker not in core.COMPANIES:
        raise ValueError("Supported tickers: NVDA, AAPL, GOOGL")
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
    out_root = Path(output_root) if output_root else core.RESULTS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = out_root / ticker / "Unified" / stamp
    folder.mkdir(parents=True, exist_ok=False)
    audit = {
        "ticker": ticker, "status": "running",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "folder": str(folder), "stages": {},
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
        price_rows, price_audit = _prices(
            ticker, price_start, end, folder / "prices", prices, log=log)
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
    parser.add_argument("--ticker", default="NVDA", choices=list(core.COMPANIES))
    parser.add_argument("--start", default=None, help="YYYY-MM-DD; default end minus news-days")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD inclusive; default today UTC")
    parser.add_argument("--news-days", type=int, default=90)
    parser.add_argument("--max-news", type=int, default=15)
    parser.add_argument("--max-filings", type=int, default=50)
    parser.add_argument("--prices", choices=["auto", "yahoo", "nasdaq"], default="auto")
    parser.add_argument("--sec-user-agent", default=None, help="Real name and contact email")
    parser.add_argument("--output-root", default=None, type=Path)
    args = parser.parse_args(argv)
    result = run(ticker=args.ticker, start=args.start, end=args.end,
                 news_days=args.news_days, max_news=args.max_news,
                 max_filings=args.max_filings, prices=args.prices,
                 agent=args.sec_user_agent, output_root=args.output_root)
    print(json.dumps({
        "status": result["status"], "run_folder": result["folder"],
        "news": result["stages"].get("news", {}).get("records"),
        "sec": result["stages"].get("sec_and_lm", {}).get("filings"),
        "market": result["stages"].get("market", {}),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
