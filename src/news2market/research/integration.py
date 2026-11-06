"""Auditable, descriptive alignment of SEC/news LM features and verified Nasdaq prices.

This module DOES NOT output trading instructions or estimate predictive accuracy.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date
import csv
import hashlib
import json
import math
from pathlib import Path

FORMS = {"8-K", "10-Q", "10-K"}
HORIZONS = (1, 3, 5)
COLUMNS = [
    "article_id", "ticker", "source_group", "form", "source", "document_date",
    "source_url", "lm_polarity", "lm_polarity_hits", "lexical_tone",
    "signal_close_date", "time_rule", "relative_return_1d", "relative_return_3d",
    "relative_return_5d", "outcome_date_1d", "outcome_date_3d", "outcome_date_5d",
]


def _bool(value):
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}


def _float(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _date(value):
    s = str(value or "").strip()
    try:
        d = date.fromisoformat(s)
        return d.isoformat()
    except ValueError:
        return None


def _group(row):
    form = str(row.get("form") or "").upper().strip()
    if form in FORMS:
        return "SEC " + form
    if str(row.get("source_type") or "").lower().startswith("sec_"):
        return "SEC other"
    return "News"


def _quality_reason(row, ticker):
    if str(row.get("ticker") or "").strip().upper() != ticker:
        return "ticker_mismatch"
    if not _bool(row.get("eligible_for_text_measurement")) or str(row.get("text_quality") or "") != "complete_body":
        return "ineligible_or_incomplete_text"
    if _bool(row.get("text_truncated")) or _bool(row.get("lm_text_truncated")):
        return "truncated_text_or_score"
    if _date(row.get("published_date")) is None:
        return "invalid_document_date"
    polarity = _float(row.get("lm_polarity"))
    if polarity is None or not -1 <= polarity <= 1:
        return "missing_or_invalid_lm_polarity"
    hits = _float(row.get("lm_polarity_hits"))
    if hits is None or hits < 0 or int(hits) != hits:
        return "missing_or_invalid_polarity_hits"
    return None


def align_features_with_prices(feature_rows, price_rows, ticker, min_directional_hits=3):
    """Return one event per eligible text plus audits, never a buy/sell forecast.

    Price tuples must have matching Nasdaq company and QQQ CLOSE values.
    First signal close strictly follows document calendar date; forward returns
    are measured from that later close. SEC public availability is unverified.
    """
    ticker = str(ticker).upper()
    if ticker not in ("NVDA", "AAPL", "GOOGL"):
        raise ValueError("Ticker must be NVDA, AAPL or GOOGL")
    if min_directional_hits < 1:
        raise ValueError("Minimum hit count must be positive")
    days = {}
    for row in price_rows:
        ds = _date(row.get("date"))
        a = _float(row.get(f"{ticker}_close"))
        b = _float(row.get("QQQ_close"))
        if ds and a is not None and b is not None and a > 0 and b > 0:
            if ds in days:
                raise ValueError("Duplicate trading session: " + ds)
            days[ds] = (a, b)
    sessions = sorted(days)
    if len(sessions) < 3:
        raise ValueError("Need at least three verified overlapping Nasdaq price sessions")

    out, reasons, sources, seen, seen_urls = [], Counter(), Counter(), set(), set()
    for row in feature_rows:
        bad = _quality_reason(row, ticker)
        if bad:
            reasons[bad] += 1
            continue
        document_id = str(row.get("article_id") or "").strip()
        source_url = str(row.get("url") or "").strip()
        identity = document_id or source_url
        if not identity:
            reasons["missing_document_identity"] += 1
            continue
        url_key = source_url.lower().rstrip("/")
        if identity in seen or (url_key and url_key in seen_urls):
            reasons["duplicate_document_id_or_url"] += 1
            continue
        seen.add(identity)
        if url_key:
            seen_urls.add(url_key)
        publication_date = _date(row.get("published_date"))
        i = bisect_right(sessions, publication_date)
        if i >= len(sessions) - 1:
            reasons["no_later_market_outcome"] += 1
            continue
        pol = _float(row.get("lm_polarity"))
        hits = int(_float(row.get("lm_polarity_hits")))
        if hits < min_directional_hits:
            tone = "insufficient_lexicon_evidence"
        elif pol > 0:
            tone = "positive_tone_not_buy_signal"
        elif pol < 0:
            tone = "negative_tone_not_sell_signal"
        else:
            tone = "balanced_lexicon_tone"
        group = _group(row)
        event = {
            "article_id": identity, "ticker": ticker, "source_group": group,
            "form": str(row.get("form") or ""), "source": str(row.get("source") or ""),
            "document_date": publication_date, "source_url": source_url,
            "lm_polarity": pol, "lm_polarity_hits": hits, "lexical_tone": tone,
            "signal_close_date": sessions[i],
            "time_rule": "first_session_close_strictly_after_document_date; public_availability_unverified",
        }
        for h in HORIZONS:
            key = f"relative_return_{h}d"
            dkey = f"outcome_date_{h}d"
            if i + h >= len(sessions):
                event[key], event[dkey] = "", ""
                continue
            asset = days[sessions[i + h]][0] / days[sessions[i]][0] - 1
            qqq = days[sessions[i + h]][1] / days[sessions[i]][1] - 1
            event[key] = round(asset - qqq, 10)
            event[dkey] = sessions[i + h]
        out.append(event)
        sources[group] += 1
    audit = {
        "status": "descriptive_exploratory_only", "ticker": ticker,
        "input_feature_records": len(feature_rows), "aligned_events": len(out),
        "excluded_records": sum(reasons.values()), "exclusion_reasons": dict(reasons),
        "source_groups": dict(sources), "unique_signal_days": len({x["signal_close_date"] for x in out}),
        "min_directional_lexicon_hits": min_directional_hits,
        "insufficient_evidence_events": sum(x["lexical_tone"] == "insufficient_lexicon_evidence" for x in out),
        "price_sessions": len(sessions), "first_price_session": sessions[0], "last_price_session": sessions[-1],
        "horizon_observations": {str(h): sum(x[f"relative_return_{h}d"] != "" for x in out) for h in HORIZONS},
        "meaning": "Relative return = asset close-to-close return minus QQQ close-to-close return over horizon; descriptive, not alpha",
        "time_rule": "First eligible close strictly later than document date, then 1/3/5 subsequent closes; not verified public availability",
        "limitations": [
            "No forward-looking buy/sell recommendation, trained model, or causal event study",
            "Lexicon score measures word balance, not investor action, economic surprise or market expectation",
            "SEC primary documents can miss exhibits and contain material boilerplate",
            "QQQ holds the analyzed companies and is not an independent market-neutral control",
            "Original Nasdaq Close/Last prices are not dividend-adjusted total returns",
            "Calendar-date availability is not independently verified; historical association can be misaligned",
            "Multiple same-date documents and overlapping horizons are not independent observations",
        ],
    }
    return out, audit


def run_market_integration(ticker, features_csv, output_folder, *, min_directional_hits=3):
    """Read a local research_features.csv and locally source-verified Nasdaq CSV pair."""
    from news2market.core import price_status, _read_price_csv, INPUTS
    ticker = ticker.upper()
    p = Path(features_csv)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.stat().st_size > 20_000_000:
        raise ValueError("Feature CSV exceeds local 20 MB audit limit")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        features = list(csv.DictReader(f))
    if not features:
        raise ValueError("No feature records found")
    state = price_status(ticker)
    if not state["ready"]:
        raise ValueError("Import verified Nasdaq " + ticker + " and QQQ CSVs in the dashboard first")
    stock, _ = _read_price_csv(INPUTS / "prices" / (ticker + ".csv"), ticker)
    qqq, _ = _read_price_csv(INPUTS / "prices" / "QQQ.csv", "QQQ")
    prices = [{"date": d, f"{ticker}_close": stock[d], "QQQ_close": qqq[d]}
              for d in sorted(set(stock) & set(qqq))]
    events, audit = align_features_with_prices(features, prices, ticker, min_directional_hits)
    audit["features_csv_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    audit["price_csv_sha256"] = {s: hashlib.sha256((INPUTS / "prices" / (s + ".csv")).read_bytes()).hexdigest()
                                for s in (ticker, "QQQ")}
    audit["prices"] = {
        sym: {k: v for k, v in state["files"][sym].items() if k in ("source", "rows", "first_date", "last_date")}
        for sym in (ticker, "QQQ")
    }
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "market_event_alignment.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(events)
    (output / "market_alignment_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    summary = [
        "# Financial Text and Subsequent QQQ-Relative Returns: Descriptive Alignment",
        "", "**Not trading advice, a validated buy/sell classifier, or evidence of causality.**", "",
        f"- Company: {ticker}; text records: {len(features)}; eligible aligned events: {len(events)}.",
        f"- Unique signal dates: {audit['unique_signal_days']}; excluded: {audit['excluded_records']}.",
        "- LM lexical tone is descriptive and **never becomes a buy/sell order**.",
        "- Each event's quality and source are preserved, with SEC forms and news shown separately.",
        "- Outcome: stock minus QQQ 1/3/5-session close-to-close returns after the first later close.",
        "- Dates alone do not prove that the event information was public by the assumed signal close.",
        "- QQQ contains each analyzed company; observations sharing dates and multi-day horizons overlap.",
        "- See market_alignment_audit.json for missingness, price coverage, source groups and other limitations.",
    ]
    (output / "market_alignment_report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return audit
