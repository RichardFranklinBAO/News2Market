"""Offline test fixtures for source-aware chronological market validation."""
import unittest

from news2market.research.validation import (
    build_daily_observations, evaluate_market_signal,
)


def event(day, target, group="News", pol=0.5, tone="positive_tone_not_buy_signal"):
    from datetime import date, timedelta
    d = date(2026, 1, 1) + timedelta(days=day)
    next_date = d + timedelta(days=1)
    return {
        "signal_close_date": d.isoformat(),
        "outcome_date_1d": next_date.isoformat(),
        "relative_return_1d": target,
        "source_group": group,
        "lm_polarity": pol, "lexical_tone": tone,
    }


class MarketValidationTests(unittest.TestCase):
    def test_aggregate_same_session_return_once(self):
        daily, ignored = build_daily_observations([
            event(0, .02, "News", .8),
            event(0, .02, "SEC 8-K", -.4, "negative_tone_not_sell_signal"),
        ])
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["news_docs"], 1)
        self.assertEqual(daily[0]["sec_docs"], 1)
        self.assertEqual(daily[0]["actual_excess_return_1d"], .02)

    def test_exclude_insufficient_lexicon(self):
        daily, ignored = build_daily_observations([
            event(0, .01, tone="insufficient_lexicon_evidence")])
        self.assertEqual(daily, [])
        self.assertEqual(ignored["days_without_informative_text"], 1)

    def test_conflicting_targets_rejected(self):
        with self.assertRaises(ValueError):
            build_daily_observations([event(0, .01), event(0, .03, "SEC 8-K")])

    def test_sparse_dates_do_not_fabricate_fit(self):
        result, pred = evaluate_market_signal([event(i, .01) for i in range(9)])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(pred, [])

    def test_chronological_holdout_and_purge(self):
        rows = [
            event(i, .008 * (i % 3 - 1) + .005 * (i % 5 - 2),
                  "News" if i % 2 else "SEC 8-K",
                  .2 if i % 3 else -.3,
                  "positive_tone_not_buy_signal" if i % 3 else "negative_tone_not_sell_signal")
            for i in range(60)
        ]
        result, predictions = evaluate_market_signal(rows)
        self.assertEqual(result["status"], "held_out_experiment_not_trading_signal")
        self.assertEqual(len(predictions), result["holdout_days"])
        self.assertLess(result["last_training_signal_date"], result["first_holdout_signal_date"])
        self.assertEqual(result["purged_training_boundary_days"], 1)

if __name__ == "__main__":
    unittest.main()
