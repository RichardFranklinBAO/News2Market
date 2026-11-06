"""Auditable direct daily-price API adapters and verified local pair cache.

No API credentials are ever written to disk, arguments or audit files.
All market pairs use one source and one adjustment basis per run.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import requests

CACHE_SECONDS = 24 * 3600
PROVIDERS = {
    "tiingo_adjusted": "Tiingo EOD adjClose (split/dividend adjusted)",
    "twelvedata_adjusted": "Twelve Data time_series adjust=all (split/dividend adjusted)",
    "yahoo_adjusted": "unofficial yfinance auto_adjust=True (adjusted close)",
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _valid_number(x):
    try:
        n = float(x)
    except (ValueError, TypeError):
        raise ValueError("Invalid daily adjusted close") from None
    if not math.isfinite(n) or n <= 0:
        raise ValueError("Nonfinite or nonpositive daily adjusted close")
    return n


def _series(symbol, records, day_key, price_key, start, end):
    values = {}
    if not isinstance(records, list):
        raise ValueError("Provider returned non-list daily prices for " + symbol)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Provider returned malformed daily price records")
        day = str(row.get(day_key) or "")[:10]
        try:
            parsed = date.fromisoformat(day)
        except ValueError:
            raise ValueError("Provider supplied invalid date for " + symbol) from None
        if parsed < start or parsed > end:
            continue
        val = _valid_number(row.get(price_key))
        if day in values:
            raise ValueError("Duplicate provider trading day for " + symbol)
        values[day] = val
    if len(values) < 3:
        raise RuntimeError("Too few usable historical sessions for " + symbol)
    return values


def _response_get(session, url, *, headers=None, params=None):
    # Never echo response text, URL with API keys, or authentication headers.
    try:
        resp = session.get(url, headers=headers, params=params, timeout=25,
                           allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError("Provider connection error (network or timeout); credentials redacted") from None
    if resp.status_code in (403, 429):
        raise RuntimeError("Provider access denied or rate limited (HTTP "
                           + str(resp.status_code) + "); no automatic retries")
    if resp.status_code != 200:
        raise RuntimeError("Provider HTTP " + str(resp.status_code))
    if len(resp.content) > 5_000_000:
        raise RuntimeError("Provider payload exceeds 5 MB safeguard")
    try:
        payload = resp.json()
    except (ValueError, TypeError):
        raise RuntimeError("Provider did not return valid JSON") from None
    return payload, hashlib.sha256(resp.content).hexdigest()


def _compose_pair(ticker, output, basis, provider, hashes, start, end):
    dates = sorted(set(output[ticker]) & set(output["QQQ"]))
    if len(dates) < 3:
        raise RuntimeError("Fewer than 3 common stock/QQQ trading sessions")
    if (end - date.fromisoformat(dates[-1])).days > 10:
        raise RuntimeError("Price source is stale by over 10 calendar days")
    paired = [{"date": d, ticker + "_close": output[ticker][d],
               "QQQ_close": output["QQQ"][d]} for d in dates]
    audit = {
        "ticker": ticker, "benchmark": "QQQ",
        "provider": provider, "price_basis": basis,
        "first_date": dates[0], "last_date": dates[-1],
        "matched_sessions": len(dates),
        "response_sha256": hashes, "sha256": hashes,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
        "adjusted_for_splits_and_dividends": True,
        "limitations": [
            "End-of-day prices do not validate event publication timestamp",
            "QQQ includes the target issuer; relative return is not pure alpha",
            "Price provider usage, redistribution and adjustment policies apply",
        ],
    }
    return paired, audit


def tiingo_pair(ticker, start, end, api_key, session=None):
    """Two direct authenticated EOD JSON requests, never expose API token."""
    if not api_key or not api_key.strip():
        raise RuntimeError("Set TIINGO_API_KEY to use Tiingo")
    session = session or requests.Session()
    output, fingerprints = {}, {}
    for sym in (ticker, "QQQ"):
        url = "https://api.tiingo.com/tiingo/daily/" + sym + "/prices"
        payload, digest = _response_get(
            session, url,
            headers={"Authorization": "Token " + api_key,
                     "Accept": "application/json"},
            params={"startDate": start.isoformat(), "endDate": end.isoformat()})
        output[sym] = _series(sym, payload, "date", "adjClose", start, end)
        fingerprints[sym] = digest
    return _compose_pair(ticker, output,
                         PROVIDERS["tiingo_adjusted"],
                         "tiingo_eod_adjusted", fingerprints, start, end)


def twelvedata_pair(ticker, start, end, api_key, session=None):
    """API-based full date-window requests with explicit dividend+split adjustment."""
    if not api_key or not api_key.strip():
        raise RuntimeError("Set TWELVEDATA_API_KEY to use Twelve Data")
    session = session or requests.Session()
    output, fingerprints = {}, {}
    for sym in (ticker, "QQQ"):
        payload, digest = _response_get(
            session, "https://api.twelvedata.com/time_series",
            params={
                "symbol": sym, "interval": "1day",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "adjust": "all", "outputsize": 5000, "apikey": api_key,
            })
        if not isinstance(payload, dict) or payload.get("status") == "error":
            raise RuntimeError("Twelve Data returned provider error or plan limitation")
        meta = payload.get("meta") or {}
        if str(meta.get("symbol") or "").upper() != sym:
            raise RuntimeError("Twelve Data symbol mismatch for " + sym)
        output[sym] = _series(sym, payload.get("values"), "datetime", "close", start, end)
        fingerprints[sym] = digest
    return _compose_pair(ticker, output,
                         PROVIDERS["twelvedata_adjusted"],
                         "twelvedata_eod_adjusted", fingerprints, start, end)


def save_pair_cache(ticker, rows, audit, root):
    """Persist only a complete API pair, atomically with hash verification."""
    name = audit.get("provider", "")
    if name not in ("tiingo_eod_adjusted", "twelvedata_eod_adjusted",
                    "yahoo_via_unofficial_yfinance"):
        return
    root = Path(root) / ticker / name
    root.mkdir(parents=True, exist_ok=True)
    raw = [["Date", ticker + "_close", "QQQ_close"]]
    for row in rows:
        raw.append([row["date"], format(_valid_number(row[ticker + "_close"]), ".16g"),
                    format(_valid_number(row["QQQ_close"]), ".16g")])
    path = root / "pair.csv"
    tmp = root / ".pair.csv.tmp"
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(raw)
    tmp.replace(path)
    meta = {
        "ticker": ticker, "provider": name,
        "price_basis": audit["price_basis"],
        "sha256": _sha(path),
        "requested_start": audit.get("requested_start"),
        "requested_end": audit.get("requested_end"),
        "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
        "response_sha256": audit.get("response_sha256", {}),
        "cached_utc": datetime.now(timezone.utc).isoformat(),
    }
    temp = root / ".manifest.tmp"
    temp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    temp.replace(root / "manifest.json")


def read_pair_cache(ticker, start, end, root, *, provider=None, now=None):
    """Require a fresh hash-verified whole pair covering requested date range."""
    now = time.time() if now is None else now
    candidates = [provider] if provider else [
        "tiingo_eod_adjusted", "twelvedata_eod_adjusted",
        "yahoo_via_unofficial_yfinance",
    ]
    for name in candidates:
        if name not in ("tiingo_eod_adjusted", "twelvedata_eod_adjusted",
                        "yahoo_via_unofficial_yfinance"):
            continue
        base = Path(root) / ticker / name
        doc = base / "manifest.json"
        path = base / "pair.csv"
        if not (doc.is_file() and path.is_file()):
            continue
        try:
            meta = json.loads(doc.read_text(encoding="utf-8"))
            age = now - datetime.fromisoformat(meta["cached_utc"]).timestamp()
            if not (0 <= age <= CACHE_SECONDS):
                continue
            if meta["ticker"] != ticker or meta["provider"] != name:
                continue
            if date.fromisoformat(meta["requested_start"]) > start:
                continue
            if date.fromisoformat(meta["requested_end"]) < end:
                continue
            if _sha(path) != meta["sha256"]:
                continue
            rows = []
            seen = set()
            with path.open(encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    d = date.fromisoformat(r["Date"])
                    if d < start or d > end:
                        continue
                    day = d.isoformat()
                    if day in seen:
                        raise ValueError("Cache has duplicate date")
                    seen.add(day)
                    rows.append({
                        "date": day, ticker + "_close": _valid_number(r[ticker + "_close"]),
                        "QQQ_close": _valid_number(r["QQQ_close"]),
                    })
            rows.sort(key=lambda x: x["date"])
            if len(rows) < 3 or (end - date.fromisoformat(rows[-1]["date"])).days > 10:
                continue
            audit = {
                "ticker": ticker, "benchmark": "QQQ",
                "provider": name, "price_basis": meta["price_basis"],
                "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
                "matched_sessions": len(rows), "cache_hit": True,
                "cached_utc": meta["cached_utc"],
                "sha256": meta.get("response_sha256") or {
                    ticker: meta["sha256"], "QQQ": meta["sha256"]},
                "cache_file_sha256": meta["sha256"],
                "response_sha256": meta.get("response_sha256", {}),
                "adjusted_for_splits_and_dividends": True,
                "limitations": ["Verified, provider-labeled 24h local cache; does not establish live price freshness",
                                "QQQ contains the target company; not pure alpha"],
            }
            return rows, audit
        except (ValueError, OSError, KeyError, TypeError, OverflowError):
            continue
    return None
