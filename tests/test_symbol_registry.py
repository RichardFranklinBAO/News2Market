"""Offline fixtures: official exchange registry and custom Nasdaq CSV ingestion."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from news2market.research import symbol_registry as sr
import run_all


def fake_registry_response(url, **kwargs):
    if "company_tickers_exchange.json" in url:
        data = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[789019, "Microsoft Corp", "MSFT", "Nasdaq"],
                     [1045810, "NVIDIA Corporation", "NVDA", "Nasdaq"],
                     [999, "Example ETF", "ETFX", "Nasdaq"]],
        }
        return Mock(status_code=200, content=json.dumps(data).encode())
    if "nasdaqlisted" in url:
        text = (
            "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
            "MSFT|Microsoft Corporation - Common Stock|Q|N|N|100|N|N\n"
            "NVDA|NVIDIA Corporation - Common Stock|Q|N|N|100|N|N\n"
            "ETFX|Example Exchange Traded Fund|Q|N|N|100|Y|N\n"
        )
    else:
        text = (
            "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
            "IBM|IBM Common Stock|N|IBM|N|100|N|IBM\n"
        )
    return Mock(status_code=200, content=text.encode())


class SymbolRegistryTests(unittest.TestCase):
    def test_symbol_canonicalization(self):
        self.assertEqual(sr.canonical_symbol(" brk.b "), "BRK-B")
        with self.assertRaises(ValueError):
            sr.canonical_symbol("QQQ")
        with self.assertRaises(ValueError):
            sr.canonical_symbol("../../anything")

    def test_sec_and_nasdaq_exact_intersection(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("requests.Session.get", side_effect=fake_registry_response):
            result = sr.resolve_stock("MSFT", "Researcher test@example.com", Path(tmp))
            self.assertEqual(result["ticker"], "MSFT")
            self.assertEqual(result["cik"], "0000789019")
            self.assertEqual(result["name"], "Microsoft Corp")
            with self.assertRaisesRegex(ValueError, "ETFX"):
                sr.resolve_stock("ETFX", "Researcher test@example.com", Path(tmp))

    def test_unknown_issuer_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("requests.Session.get", side_effect=fake_registry_response):
            with self.assertRaises(ValueError):
                sr.resolve_stock("FAKE", "Researcher test@example.com", Path(tmp))

    def test_canonical_nasdaq_files_can_be_registered_by_explicit_confirmation(self):
        from news2market import core
        from news2market.research.symbol_registry import resolve_stock
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "inputs" / "prices"
            base.mkdir(parents=True)
            original = ("Date,Close/Last,Volume\n"
                        "11/02/2026,$300,100\n"
                        "11/03/2026,$301,200\n"
                        "11/04/2026,$302,200\n")
            (base/"MSFT.csv").write_text(original)
            (base/"QQQ.csv").write_text(original.replace("$300", "$500"))
            with patch.object(core, "INPUTS", Path(tmp) / "inputs"):
                self.assertFalse(core._nasdaq_evidence("MSFT", base/"MSFT.csv"))
                registered = run_all.import_nasdaq_pair(
                    "MSFT", base/"MSFT.csv", base/"QQQ.csv",
                    confirmed_nasdaq=True,
                )
                self.assertEqual(registered["MSFT"]["rows"], 3)
                self.assertTrue(core._nasdaq_evidence("MSFT", base/"MSFT.csv"))
                self.assertTrue(core._nasdaq_evidence("QQQ", base/"QQQ.csv"))
                rows, audit = run_all._price_rows_from_nasdaq("MSFT")
                self.assertEqual(len(rows), 3)
                self.assertEqual(audit["provider"], "nasdaq_user_verified_local")

    def test_nasdaq_pair_attribution_requires_user_confirmation(self):
        from news2market import core
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "HistoricalData_msft.csv"
            b = Path(tmp) / "HistoricalData_qqq.csv"
            a.write_text("Date,Close/Last,Volume\n11/02/2026,$300,100\n"
                         "11/03/2026,$301,200\n11/04/2026,$302,200\n")
            b.write_text("Date,Close/Last,Volume\n11/02/2026,$500,100\n"
                         "11/03/2026,$501,200\n11/04/2026,$502,200\n")
            with patch.object(core, "INPUTS", Path(tmp) / "inputs"):
                with self.assertRaisesRegex(ValueError, "confirm-nasdaq"):
                    run_all.import_nasdaq_pair("MSFT", a, b)
                result = run_all.import_nasdaq_pair(
                    "MSFT", a, b, confirmed_nasdaq=True)
                self.assertEqual(result["MSFT"]["rows"], 3)
                rows, audit = run_all._price_rows_from_nasdaq("MSFT")
                self.assertEqual(len(rows), 3)
                self.assertEqual(audit["provider"], "nasdaq_user_verified_local")
                self.assertTrue((core.INPUTS / "prices" / "MSFT.csv").exists())


if __name__ == "__main__":
    unittest.main()
