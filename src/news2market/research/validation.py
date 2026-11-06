"""Time-ordered *experimental* validation of incremental LM information.

Quality control and date alignment are performed upstream in integration.py.
Each distinct signal date contributes at most one 1-session return observation.
The fixed Ridge specification is compared to a train-mean no-text baseline.
Never treat a result as a buy/sell recommendation or causal market effect.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date
import json
import math
from pathlib import Path

HOLDOUT_FIELDS = [
    "signal_date", "outcome_date", "actual_excess_return_1d",
    "text_model_forecast", "no_text_baseline_forecast",
    "news_tone_mean", "sec_tone_mean", "news_docs", "sec_docs",
]


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _mean(values):
    return sum(values) / len(values)


def build_daily_observations(events):
    """Aggregate repeated same-date texts WITHOUT duplicating the return target."""
    grouped = defaultdict(list)
    for event in events:
        day = str(event.get("signal_close_date") or "")
        outcome = str(event.get("outcome_date_1d") or "")
        result = _number(event.get("relative_return_1d"))
        try:
            date.fromisoformat(day)
            date.fromisoformat(outcome)
        except ValueError:
            continue
        if result is None or outcome <= day:
            continue
        grouped[day].append(event)

    observations = []
    ignored = Counter()
    for day in sorted(grouped):
        group = grouped[day]
        targets = [_number(e.get("relative_return_1d")) for e in group]
        outcome_dates = {e.get("outcome_date_1d") for e in group}
        if len(outcome_dates) != 1 or any(abs(v - targets[0]) > 1e-8 for v in targets):
            raise ValueError("Conflicting same-session market outcomes: " + day)
        news, sec = [], []
        for e in group:
            tone = str(e.get("lexical_tone") or "")
            polarity = _number(e.get("lm_polarity"))
            if tone not in ("positive_tone_not_buy_signal",
                            "negative_tone_not_sell_signal", "balanced_lexicon_tone"):
                ignored["insufficient_lexicon_evidence"] += 1
                continue
            if polarity is None or not -1 <= polarity <= 1:
                ignored["invalid_polarity"] += 1
                continue
            if str(e.get("source_group") or "").startswith("SEC "):
                sec.append(polarity)
            elif e.get("source_group") == "News":
                news.append(polarity)
            else:
                ignored["unknown_source"] += 1
        if not news and not sec:
            ignored["days_without_informative_text"] += 1
            continue
        observations.append({
            "signal_date": day, "outcome_date": next(iter(outcome_dates)),
            "actual_excess_return_1d": targets[0],
            "news_tone_mean": _mean(news) if news else 0.0,
            "sec_tone_mean": _mean(sec) if sec else 0.0,
            "news_docs": len(news), "sec_docs": len(sec),
        })
    return observations, dict(ignored)


def _features(row):
    # Missing sources are explicitly identified rather than interpreted as neutrality.
    return [row["news_tone_mean"], row["sec_tone_mean"],
            float(row["news_docs"] > 0), float(row["sec_docs"] > 0)]


def _scores(actual, forecast):
    from math import sqrt
    errors = [a - p for a, p in zip(actual, forecast)]
    directional_pairs = [(a, p) for a, p in zip(actual, forecast)
                         if abs(a) > 1e-12]
    return {
        "rmse": round(sqrt(_mean([e * e for e in errors])), 8),
        "mae": round(_mean([abs(e) for e in errors]), 8),
        "direction_accuracy_nonzero_outcomes": (
            round(_mean([int((a > 0) == (p > 0)) for a, p in directional_pairs]), 6)
            if directional_pairs else None),
        "nonzero_outcome_count": len(directional_pairs),
    }


def evaluate_market_signal(events, *, min_unique_days=40, min_train_days=25,
                           min_test_days=10):
    """One fixed, source-aware model with chronological holdout and no tuning.

    Requiring many *independent dates*, not many filings, avoids pseudo-replication.
    The train/test boundary is purged when a train target reaches the test date.
    """
    if min_unique_days < min_train_days + min_test_days:
        raise ValueError("min_unique_days must cover train and holdout")
    rows, ignored = build_daily_observations(events)
    result = {
        "status": "insufficient_evidence",
        "method": "fixed Ridge(alpha=10), four source-specific features, 1-day excess return",
        "baseline": "historical mean 1-day excess return of training signal days; no text features",
        "unit_of_analysis": "unique signal session, not individual news articles or SEC filings",
        "n_informative_distinct_days": len(rows),
        "minimum_unique_days": min_unique_days,
        "minimum_training_days": min_train_days,
        "minimum_holdout_days": min_test_days,
        "excluded_from_daily_features": ignored,
        "limitations": [
            "Descriptive experimental validation only: not a calibrated buy/sell signal",
            "Date-only public availability assumptions remain unverified",
            "The comparison is conditional on observed eligible text-event dates, not all market days",
            "Daily aggregation prevents same-date duplication; adjacent events may still be dependent",
            "QQQ includes the target stock and Close/Last data are not total-return adjusted",
            "Source-specific polarity has not been validated as an economic-surprise measure",
            "One chronological holdout is not a stable multi-period performance evaluation",
            "Fixed model, thresholds and exploratory design are not pre-registered",
            "No transaction costs, risk adjustments or independently verified market timestamps",
        ],
    }
    if len(rows) < min_unique_days:
        result["reason"] = "Too few independent signal dates for a meaningful holdout"
        return result, []

    split = int(len(rows) * 0.70)
    split = max(split, min_train_days + 1)
    if len(rows) - split < min_test_days:
        result["reason"] = "Not enough distinct dates in held-out period"
        return result, []
    test = rows[split:]
    train = rows[:split]
    # Purge any overlapping training label whose close is on/after first test signal.
    first_test_date = test[0]["signal_date"]
    while train and train[-1]["outcome_date"] >= first_test_date:
        train.pop()
    result.update({
        "training_days": len(train), "holdout_days": len(test),
        "first_training_signal_date": rows[0]["signal_date"],
        "last_training_signal_date": train[-1]["signal_date"] if train else None,
        "first_holdout_signal_date": first_test_date,
        "last_holdout_signal_date": test[-1]["signal_date"],
        "purged_training_boundary_days": split - len(train),
        "train_news_dates": sum(r["news_docs"] > 0 for r in train),
        "train_sec_dates": sum(r["sec_docs"] > 0 for r in train),
    })
    if len(train) < min_train_days:
        result["reason"] = "Insufficient training days after temporal boundary purge"
        return result, []
    if sum(any(abs(x) > 1e-12 for x in _features(r)[:2]) for r in train) < 5:
        result["reason"] = "Not enough training days with nonzero LM tone"
        return result, []
    if len(set(tuple(_features(r)) for r in train)) < 3:
        result["reason"] = "Insufficient variation in training text features"
        return result, []

    from sklearn.linear_model import Ridge
    x_train = [_features(r) for r in train]
    y_train = [r["actual_excess_return_1d"] for r in train]
    x_test = [_features(r) for r in test]
    y_test = [r["actual_excess_return_1d"] for r in test]
    model = Ridge(alpha=10.0, fit_intercept=True)
    model.fit(x_train, y_train)
    forecast = [float(x) for x in model.predict(x_test)]
    baseline = [_mean(y_train)] * len(test)
    text_scores = _scores(y_test, forecast)
    baseline_scores = _scores(y_test, baseline)
    predictions = [{
        **r, "text_model_forecast": round(p, 10),
        "no_text_baseline_forecast": round(b, 10),
    } for r, p, b in zip(test, forecast, baseline)]
    improvement = baseline_scores["rmse"] - text_scores["rmse"]
    result.update({
        "status": "held_out_experiment_not_trading_signal",
        "text_model": text_scores, "no_text_baseline": baseline_scores,
        "rmse_improvement_vs_no_text": round(improvement, 8),
        "directional_accuracy_improvement_vs_no_text": (
            round(text_scores["direction_accuracy_nonzero_outcomes"]
                  - baseline_scores["direction_accuracy_nonzero_outcomes"], 6)
            if text_scores["direction_accuracy_nonzero_outcomes"] is not None
            and baseline_scores["direction_accuracy_nonzero_outcomes"] is not None else None),
        "model_coefficients": {
            "news_tone_mean": round(float(model.coef_[0]), 10),
            "sec_tone_mean": round(float(model.coef_[1]), 10),
            "has_news": round(float(model.coef_[2]), 10),
            "has_sec": round(float(model.coef_[3]), 10),
            "intercept": round(float(model.intercept_), 10),
        },
        "interpretation": ("Lower holdout RMSE than a no-text baseline is a tentative "
                           "incremental-information diagnostic, not proof of tradable alpha "
                           "or robust forecasting power."),
        "beat_no_text_on_rmse": bool(improvement > 0),
    })
    return result, predictions


def write_market_validation(events, output_folder):
    """Always produce an honest audit and a header-only predictions CSV if untestable."""
    result, predictions = evaluate_market_signal(events)
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "market_signal_validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    with (folder / "market_holdout_predictions.csv").open(
            "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HOLDOUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(predictions)
    return result
