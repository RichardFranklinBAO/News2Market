"""Resolve actual SEC-registered U.S.-exchange stock symbols against live listings.

Only exact SEC ticker+CIK+exchange links and Nasdaq Trader non-ETF/non-test
listings pass. Fail closed when sources are unavailable; cached snapshots expire.
This is a CURRENT-listing check, not a historical listing or corporate identity
verification of individual articles.
"""
from __future__ import annotations
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import time

import requests

SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
LISTINGS = {
    "NASDAQ": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "OTHER": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}
MAX_BYTES = 6_000_000
MAX_AGE_SECONDS = 24 * 3600
ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "NYSE AMERICAN", "NYSE MKT", "NYSE ARCA",
                     "CBOE", "CBOE BZX", "IEX", "IEXG", "BATS"}


def canonical_symbol(symbol):
    s = str(symbol or "").strip().upper().replace("/", "-").replace(".", "-")
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,5}(?:-[A-Z0-9]{1,3})?", s):
        raise ValueError("Ticker must be a real US stock symbol, e.g. NVDA, MSFT, AMD, BRK.B")
    if s == "QQQ":
        raise ValueError("QQQ is the benchmark ETF, not a supported individual-stock target")
    return s


def _cache_fetch(url, path, session, *, ttl=MAX_AGE_SECONDS):
    path = Path(path)
    if path.exists() and path.stat().st_size > 0 and time.time() - path.stat().st_mtime < ttl:
        return path.read_text(encoding="utf-8-sig"), "fresh_cached"
    # Do not silently use stale listings to claim a currently tradable stock.
    response = session.get(url, timeout=20, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f"Symbol registry unavailable (HTTP {response.status_code}); no unverified ticker accepted")
    raw = response.content
    if not 30 <= len(raw) <= MAX_BYTES:
        raise ValueError("Unexpected symbol registry response size")
    data = raw.decode("utf-8-sig")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(data, encoding="utf-8")
    temp.replace(path)
    return data, "live"


def _sec_table(text):
    payload = json.loads(text)
    fields = payload.get("fields")
    data = payload.get("data")
    if not isinstance(fields, list) or not isinstance(data, list):
        raise ValueError("Unrecognized official SEC ticker/exchange registry")
    keys = [str(x).lower() for x in fields]
    required = {"cik", "name", "ticker", "exchange"}
    if not required.issubset(keys):
        raise ValueError("SEC registry missing required columns")
    return [dict(zip(keys, record)) for record in data if isinstance(record, list)]


def _nasdaq_directory(text, *, is_other=False):
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    if not reader.fieldnames:
        raise ValueError("Empty Nasdaq Trader symbol directory")
    symbol_field = "ACT Symbol" if is_other else "Symbol"
    if symbol_field not in reader.fieldnames or "ETF" not in reader.fieldnames:
        raise ValueError("Unexpected Nasdaq Trader symbol directory format")
    result = {}
    for row in reader:
        ticker = str(row.get(symbol_field) or "").strip().upper()
        if not ticker or ticker.startswith("File Creation Time"):
            continue
        if str(row.get("Test Issue") or "N").strip() != "N":
            continue
        # ETF flag is essential: SEC ticker mappings also contain many funds.
        if str(row.get("ETF") or "").strip() != "N":
            continue
        name = str(row.get("Security Name") or "")
        # Exchange-listed securities include warrants, rights and units.
        # Exclude obvious non-share instruments, acknowledge residual ambiguity.
        if re.search(r"\b(warrant|right to buy|preferred|depositary shares representing preferred|"
                     r"unit[s]? (?:consisting|comprising)|note[s]? due|debenture[s]?)\b",
                     name, re.IGNORECASE):
            continue
        normalized = ticker.replace("/", "-").replace(".", "-")
        result[normalized] = {
            "listing_symbol": ticker, "listing_name": name,
            "listing_exchange": (row.get("Exchange") if is_other else "NASDAQ"),
        }
    if not result:
        raise ValueError("Empty usable Nasdaq Trader directory")
    return result


def resolve_stock(symbol, agent, cache_dir):
    """Return verified CIK/company profile for current US-exchange-listed shares."""
    sym = canonical_symbol(symbol)
    if not agent or "@" not in agent:
        raise ValueError("SEC ticker lookup requires identified User-Agent with contact email")
    session = requests.Session()
    session.trust_env = True
    session.headers.update({"User-Agent": agent, "Accept": "application/json,text/plain"})
    root = Path(cache_dir)
    sec_text, sec_mode = _cache_fetch(SEC_URL, root / "sec_company_tickers_exchange.json", session)
    sec_rows = [row for row in _sec_table(sec_text)
                if str(row["ticker"]).upper().replace(".", "-").replace("/", "-") == sym
                and str(row["exchange"]).upper() in ALLOWED_EXCHANGES]
    if not sec_rows:
        raise ValueError(f"{sym} is not an exact SEC-listed US-exchange ticker with usable CIK")
    listing_rows = {}
    modes = {}
    for key, url in LISTINGS.items():
        listing_text, mode = _cache_fetch(url, root / f"nasdaqtrader_{key.lower()}.txt", session)
        listing_rows.update(_nasdaq_directory(listing_text, is_other=(key == "OTHER")))
        modes[key] = mode
    listed = listing_rows.get(sym)
    if not listed:
        raise ValueError(f"{sym} not found as an eligible non-ETF, non-test Nasdaq Trader listing")
    if len({str(x["cik"]) for x in sec_rows}) != 1:
        raise ValueError(f"Ambiguous SEC CIK for {sym}; refusing automatic issuer mapping")
    row = sec_rows[0]
    cik = str(int(row["cik"])).zfill(10)
    name = str(row["name"]).strip()
    if not name:
        raise ValueError(f"SEC issuer name missing for {sym}")
    # Generic news-query alias is heuristic; not verified article-level entity matching.
    base = re.split(r"\s+(?:Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|PLC)\b",
                    name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    short = base.split()[0] if base else name.split()[0]
    aliases = [a for a in (sym, base, name, short if len(short) >= 4 else "")
               if len(a) >= 3]
    return {
        "ticker": sym, "name": name, "cik": cik,
        "exchange": str(row["exchange"]), "nasdaq_listing": listed,
        "lookup_source": "SEC company_tickers_exchange and Nasdaq Trader symbol directories",
        "lookup_modes": {"sec": sec_mode, **modes},
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "query": base or name, "aliases": list(dict.fromkeys(aliases)),
        "official_feed": None, "official_host": "",
        "has_issuer_scraper": False,
        "limitations": [
            "A current listing does not validate every collected news article or historical trading date",
            "Nasdaq Trader ETF/test filtering cannot perfectly identify every equity instrument subtype",
            "Ticker, CIK and issuer names can change after corporate actions",
        ],
    }
