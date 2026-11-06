"""Offline direct-price API and cache tests: no live tokens or requests."""
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import tempfile
import unittest

from news2market.research.price_providers import (
    tiingo_pair, twelvedata_pair, save_pair_cache, read_pair_cache
)


class FakeSession:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        body = next(self.payloads)
        resp = Mock()
        resp.status_code = body.get("http_status", 200) if isinstance(body, dict) else 200
        payload = body.get("payload", body) if isinstance(body, dict) else body
        import json
        resp.content = json.dumps(payload).encode()
        resp.json.return_value = payload
        return resp


class DirectProvidersTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 1, 1)
        self.end = date(2026, 1, 9)

    def test_tiingo_adjusted_pair(self):
        dates = ["2026-01-05", "2026-01-06", "2026-01-07"]
        payload = [{"date": d + "T00:00:00Z", "adjClose": float(i+100)}
                   for i, d in enumerate(dates)]
        session = FakeSession([payload, payload])
        rows, audit = tiingo_pair("TSLA", self.start, self.end, "hidden-token", session)
        self.assertEqual(len(rows), 3)
        self.assertEqual(audit["provider"], "tiingo_eod_adjusted")
        self.assertIn("QQQ", audit["sha256"])
        self.assertEqual(session.calls[0][1]["headers"]["Authorization"], "Token hidden-token")
        self.assertNotIn("hidden-token", str(audit))

    def test_twelvedata_explicit_adjustment_and_meta(self):
        values = [{"datetime": d, "close": str(100+i)} for i, d in
                  enumerate(["2026-01-05", "2026-01-06", "2026-01-07"])]
        session = FakeSession([
            {"meta": {"symbol": "TSLA"}, "values": values},
            {"meta": {"symbol": "QQQ"}, "values": values},
        ])
        rows, audit = twelvedata_pair("TSLA", self.start, self.end, "hidden-token", session)
        self.assertEqual(len(rows), 3)
        self.assertEqual(session.calls[0][1]["params"]["adjust"], "all")
        self.assertNotIn("hidden-token", str(audit))

    def test_rate_limit_stops(self):
        session = FakeSession([{"http_status": 429, "payload": {"message": "limit"}}])
        with self.assertRaisesRegex(RuntimeError, "rate limited"):
            tiingo_pair("TSLA", self.start, self.end, "secret", session)
        self.assertEqual(len(session.calls), 1)

    def test_cache_coverage_and_integrity(self):
        rows = [{"date": "2026-01-05", "TSLA_close": 100, "QQQ_close": 200},
                {"date": "2026-01-06", "TSLA_close": 101, "QQQ_close": 201},
                {"date": "2026-01-07", "TSLA_close": 102, "QQQ_close": 202}]
        audit = {
            "provider": "tiingo_eod_adjusted",
            "price_basis": "Tiingo EOD adjClose",
            "requested_start": "2026-01-01",
            "requested_end": "2026-01-09",
            "response_sha256": {"TSLA": "a"*64, "QQQ": "b"*64},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_pair_cache("TSLA", rows, audit, root)
            got = read_pair_cache("TSLA", self.start, self.end, root)
            self.assertIsNotNone(got)
            self.assertTrue(got[1]["cache_hit"])
            self.assertEqual(got[1]["sha256"]["TSLA"], "a"*64)
            file = root/"TSLA"/"tiingo_eod_adjusted"/"pair.csv"
            file.write_text(file.read_text()+"tamper")
            self.assertIsNone(read_pair_cache("TSLA", self.start, self.end, root))

    def test_missing_adjusted_close_fails_closed(self):
        payload = [{"date": "2026-01-05", "close": 100},
                   {"date": "2026-01-06", "close": 101},
                   {"date": "2026-01-07", "close": 102}]
        with self.assertRaisesRegex(ValueError, "Invalid daily adjusted close"):
            tiingo_pair("TSLA", self.start, self.end, "key", FakeSession([payload]))


if __name__ == "__main__":
    unittest.main()
