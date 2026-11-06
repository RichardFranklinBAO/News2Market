"""Synthetic, network-free tests for the unified entrypoint."""
import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import run_all


class UnifiedRunnerTests(unittest.TestCase):
    def test_price_source_prefers_yahoo(self):
        response = ([{"date": "2026-01-06", "NVDA_close": 120,
                      "QQQ_close": 100}], {"provider": "yahoo_via_unofficial_yfinance"})
        with patch.object(run_all, "_price_rows_from_yahoo", return_value=response) as yahoo, \
             patch.object(run_all, "_price_rows_from_nasdaq") as nasdaq:
            rows, audit = run_all._prices("NVDA", date(2026, 1, 1),
                                          date(2026, 1, 9), Path("/tmp"), "auto")
        self.assertEqual(audit["provider"], "yahoo_via_unofficial_yfinance")
        yahoo.assert_called_once()
        nasdaq.assert_not_called()

    def test_yahoo_failure_falls_back_and_audits_source(self):
        response = ([{"date": "2026-01-06", "NVDA_close": 120,
                      "QQQ_close": 100}], {"provider": "nasdaq_user_verified_local"})
        with patch.object(run_all, "_price_rows_from_yahoo", side_effect=RuntimeError("blocked")), \
             patch.object(run_all, "_price_rows_from_nasdaq", return_value=response):
            _, audit = run_all._prices("NVDA", date(2026, 1, 1),
                                       date(2026, 1, 9), Path("/tmp"), "auto")
        self.assertEqual(audit["provider"], "nasdaq_user_verified_local")
        self.assertIn("Yahoo: blocked", audit["failed_yahoo_attempt"][0])

    def test_yahoo_only_failure_does_not_use_nasdaq(self):
        with patch.object(run_all, "_price_rows_from_yahoo", side_effect=RuntimeError("blocked")), \
             patch.object(run_all, "_price_rows_from_nasdaq") as nasdaq:
            with self.assertRaisesRegex(RuntimeError, "blocked"):
                run_all._prices("NVDA", date(2026, 1, 1),
                                date(2026, 1, 9), Path("/tmp"), "yahoo")
            nasdaq.assert_not_called()

    def test_invalid_sec_agent_fails_before_network(self):
        with patch.object(run_all.core, "ensure_lm_dictionary") as lm:
            with self.assertRaisesRegex(ValueError, "N2M_SEC_USER_AGENT"):
                run_all.run(agent="not-an-email")
            lm.assert_not_called()

    def test_one_command_plumbs_all_stages_with_mocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_events = [
                {"date": "2026-01-06", "NVDA_close": 102, "QQQ_close": 101},
                {"date": "2026-01-07", "NVDA_close": 103, "QQQ_close": 101},
                {"date": "2026-01-08", "NVDA_close": 104, "QQQ_close": 102},
            ]
            def fake_sec(args):
                folder = root / "mock_sec"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "research_features.csv").write_text(
                    "article_id,ticker,published_date,source_type\n"
                    "one,NVDA,2026-01-05,sec_filing_primary_document\n", encoding="utf-8")
                return folder, {"disclosures_selected": 1,
                                "research_scores": {"text_scored_records": 1}}
            price_audit = {
                "provider": "mock_yahoo", "sha256": {"NVDA": "a"*64, "QQQ": "b"*64},
                "first_date": "2026-01-06", "last_date": "2026-01-08",
            }
            verified = {
                "ticker": "NVDA", "name": "NVIDIA Corporation",
                "cik": "0001045810", "query": "NVIDIA", "aliases": ["NVDA", "NVIDIA"],
                "official_host": "nvidianews.nvidia.com",
            }
            with patch.object(run_all.core, "ensure_lm_dictionary"), \
                 patch("news2market.research.symbol_registry.resolve_stock", return_value=verified), \
                 patch.object(run_all, "_news_rows", return_value=([], {})), \
                 patch.object(run_all.research_cli, "command_sec", side_effect=fake_sec), \
                 patch.object(run_all, "_prices", return_value=(fake_events, price_audit)), \
                 patch.object(run_all, "run_market_integration", return_value={
                     "aligned_events": 1, "source_groups": {"SEC 8-K": 1},
                     "predictive_validation": {"status": "insufficient_evidence"},
                 }):
                result = run_all.run(ticker="NVDA", start="2026-01-01",
                                     end="2026-01-08", agent="Tester test@example.com",
                                     output_root=root, log=lambda msg: None)
            self.assertEqual(result["status"], "complete_with_limitations")
            self.assertTrue((Path(result["folder"]) / "unified_audit.json").exists())
            self.assertEqual(result["stages"]["market"]["aligned_events"], 1)


if __name__ == "__main__":
    unittest.main()
