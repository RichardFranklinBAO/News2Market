"""Offline tests for News2Market final application; synthetic fixtures are ONLY test fixtures."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date,timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from news2market import core as v


class CompanySwitchTests(unittest.TestCase):
    def test_exact_three(self):
        self.assertEqual(set(v.COMPANIES),{"NVDA","AAPL","GOOGL"})
        self.assertIn("Alphabet",v.COMPANIES["GOOGL"]["name"])
        self.assertEqual({x['ticker'] for x in v.supported_companies()},set(v.COMPANIES))

    def test_reject_arbitrary_ticker(self):
        with self.assertRaises(ValueError):v.validate_options(ticker="NOT_A_TICKER")

    def test_apple_food_vs_company(self):
        apple=v.COMPANIES["AAPL"]
        self.assertFalse(v.financial_text_relevance("Apple orchard harvest celebrated", "Cider and fruit",apple))
        self.assertTrue(v.financial_text_relevance("Apple announces new iPhone", "Technology launch",apple))

    def test_google_alphabet_both_match(self):
        google=v.COMPANIES["GOOGL"]
        self.assertTrue(v.financial_text_relevance("Alphabet announces results","",google))
        self.assertTrue(v.financial_text_relevance("Google Cloud usage expands","",google))
        self.assertFalse(v.financial_text_relevance("Apple iPhone sales","",google))

    def test_yahoo_option_rejected(self):
        with self.assertRaisesRegex(ValueError, "price_mode"):
            v.validate_options(ticker="NVDA",price_mode="yahoo")

    def test_nasdaq_csv_validation(self):
        sample="Date,Close/Last,Volume\n11/02/2026,$200.00,1000\n11/03/2026,$210.00,1500\n11/04/2026,$205.00,1600\n"
        result=v.validate_nasdaq_csv_text(sample,"AAPL")
        self.assertEqual(result["row_count"],3)
        self.assertEqual(result["last_date"],"2026-11-04")
        self.assertFalse(result["cash_dividend_adjusted"])
        for invalid in ("Date,Adj Close\n11/02/2026,200", "Date,Close/Last\n11/02/2026,$100", 
                        "Date,Close/Last\n11/02/2026,$100\n11/02/2026,$101\n11/03/2026,$102\n"):
            with self.assertRaises(ValueError):v.validate_nasdaq_csv_text(invalid,"AAPL")

    def test_import_and_nasdaq_only_pair(self):
        sample="Date,Close/Last,Volume\n11/02/2026,$200.00,1000\n11/03/2026,$210.00,1500\n11/04/2026,$205.00,1600\n"
        with tempfile.TemporaryDirectory() as tmp:
            old=v.INPUTS; v.INPUTS=Path(tmp)
            try:
                with self.assertRaisesRegex(ValueError,"Confirm"):
                    v.import_nasdaq_csv("AAPL",sample,False)
                self.assertFalse((v.INPUTS/"prices"/"AAPL.csv").exists())
                v.import_nasdaq_csv("AAPL",sample,True)
                v.import_nasdaq_csv("QQQ",sample.replace("$200.00","$300.00"),True)
                self.assertTrue(v.price_status("AAPL")["ready"])
                rows,audit=v.prices_for_pair("AAPL",date(2026,11,1),date(2026,11,4),"nasdaq_csv",log=lambda m:None)
                self.assertEqual(len(rows),3)
                self.assertEqual(audit["provider"],"nasdaq_local_csv")
                self.assertTrue(audit["no_yahoo"])
                self.assertEqual(rows[-1]["AAPL_close"],205)
                with self.assertRaises(ValueError):v.import_nasdaq_csv("AAPL","Date,Close\n",True)
                self.assertTrue(v.price_status("AAPL")["ready"])
            finally:v.INPUTS=old

    def test_no_partial_price_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=v.INPUTS;v.INPUTS=Path(tmp)
            try:
                v.import_nasdaq_csv("AAPL","Date,Close/Last\n11/02/2026,$100\n11/03/2026,$101\n11/04/2026,$102\n",True)
                with self.assertRaisesRegex(RuntimeError,"QQQ"):
                    v.prices_for_pair("AAPL",date(2026,11,1),date(2026,11,4),"nasdaq_csv",log=lambda m:None)
            finally:v.INPUTS=old

    def test_sibling_verified_nasdaq_auto_reuse(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            original_root=v.ROOT;original_inputs=v.INPUTS
            base=Path(tmp); old_prices=base/"News2Market"/"Inputs"/"prices";old_prices.mkdir(parents=True)
            fresh=base/"News2Market_A";fresh.mkdir()
            sample="Date,Close/Last\n11/02/2026,$100\n11/03/2026,$101\n11/04/2026,$102\n"
            manifest={}
            for symbol in ("NVDA","QQQ"):
                raw=sample.encode("utf-8")
                (old_prices/f"{symbol}.csv").write_bytes(raw)
                manifest[symbol]={"source":"User-provided Nasdaq historical-data CSV","sha256":hashlib.sha256(raw).hexdigest(),
                                  "rows":3,"first_date":"2026-11-02","last_date":"2026-11-04"}
            (old_prices/"SOURCE_MANIFEST.json").write_text(json.dumps(manifest))
            try:
                v.ROOT=fresh;v.INPUTS=fresh/"inputs"
                self.assertFalse(v.price_status("NVDA")["ready"])
                v._reuse_previous_project_csv("NVDA",log=lambda m:None)
                v._reuse_previous_project_csv("QQQ",log=lambda m:None)
                self.assertTrue(v.price_status("NVDA")["ready"])
                self.assertTrue((fresh/"inputs"/"prices"/"NVDA.csv").exists())
                self.assertTrue((old_prices/"NVDA.csv").exists())
            finally:v.ROOT=original_root;v.INPUTS=original_inputs

    def test_dictionary_preflight_blocks_network_without_source(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            original=v.INPUTS
            v.INPUTS=Path(tmp)/"inputs"
            try:
                self.assertFalse(v.lm_dictionary_status()["ready"])
                with patch.object(v,"ensure_lm_dictionary",side_effect=RuntimeError("Official LM dictionary not installed")):
                    def fail_if_called(*args, **kwargs):
                        raise AssertionError("Market/news stages must not be called")
                    with self.assertRaisesRegex(RuntimeError,"Official LM dictionary"):
                        v.run_pipeline(v.validate_options(),news_loader=fail_if_called,
                            price_loader=fail_if_called,root_output=tmp,log=lambda msg:None)
                self.assertFalse((Path(tmp)/"NVDA"/"Runs").exists())
            finally:
                v.INPUTS=original

    def test_dictionary_status_reports_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_inputs,original_root=v.INPUTS,v.ROOT
            try:
                v.INPUTS=Path(tmp)/"inputs";v.ROOT=Path(tmp)/"News2Market_B"
                result=v.lm_dictionary_status()
                self.assertFalse(result["ready"])
                self.assertEqual(result["source"],"missing")
                self.assertIn("sraf.nd.edu",result["official_download"])
            finally:
                v.INPUTS=original_inputs;v.ROOT=original_root

    def test_package_entrypoint_and_dashboard_asset(self):
        """Prevent the root-to-package refactor from breaking the public command."""
        import subprocess
        from news2market.web import UI_HTML
        self.assertTrue(UI_HTML.is_file())
        result=subprocess.run([sys.executable, "-m", "news2market", "--help"],
               cwd=Path(__file__).resolve().parents[1], check=True,
               capture_output=True, text=True, timeout=15)
        self.assertIn("--web", result.stdout)
        self.assertIn("--ticker", result.stdout)

    def test_clean_package_layout(self):
        repo=Path(__file__).resolve().parents[1]
        for old_entry in ("app.py", "core.py", "web.py"):
            self.assertFalse((repo/old_entry).exists())
            self.assertTrue((repo/"src"/"news2market"/old_entry).exists())

    def test_stage_files_are_named_by_function(self):
        """Avoid old sequence numbers and verify key dynamic imports."""
        import re
        scripts=Path(__file__).resolve().parents[1]/"scripts"
        groups=("shared", "step_01_collect", "step_02_prepare",
                "step_03_nlp", "step_04_market", "step_05_report")
        self.assertTrue(all((scripts / p / "__init__.py").is_file() for p in groups))
        self.assertEqual({p.name for p in scripts.glob("*.py")}, {"__init__.py"})
        self.assertTrue(v.SCRIPT_NAMES.issubset(set(v.STAGE_MODULES)))
        self.assertEqual(
            v.STAGE_MODULES["nasdaq_csv_parser.py"],
            "scripts.step_04_market.nasdaq_csv_parser")
        self.assertTrue(callable(v.load_script_module(
            "nasdaq_csv_parser.py","n2m_price_smoke").parse_price_csv))
        self.assertTrue(callable(v.load_script_module(
            "news_feed_discovery.py","n2m_feed_smoke").discover))

    def test_lowercase_directory_convention(self):
        """Tracked root paths use lowercase names; old input folders are legacy only."""
        repo=Path(__file__).resolve().parents[1]
        root_names={p.name for p in repo.iterdir()}
        self.assertTrue({"scripts","inputs","docs","src","tests"}.issubset(root_names))
        self.assertTrue({"Scripts","Inputs"}.isdisjoint(root_names))
        self.assertEqual(v.SCRIPTS,repo/"scripts")
        self.assertEqual(v.INPUTS,repo/"inputs")

    def test_webpage_english_only_and_no_yahoo(self):
        html=(Path(__file__).resolve().parents[1]/"src"/"news2market"/"ui"/"index.html").read_text(encoding="utf-8")
        self.assertIn('lang="en"',html)
        self.assertIn("Import selected CSV files",html)
        self.assertIn("official Nasdaq",html)
        self.assertNotIn('value="yahoo"',html)
        import re
        self.assertIsNone(re.search(r"[\u4e00-\u9fff]",html))


class FullPipelineTests(unittest.TestCase):
    def fake_prices(self,ticker,start,end,mode,log=print):
        out=[];d=date(2026,10,1);i=0
        while d<=end:
            if d.weekday()<5:
                p=100*(1+0.001*i+0.00015*(i%7))
                q=100*(1+0.0007*i+0.00005*(i%5))
                out.append({"date":d.isoformat(),f"{ticker}_close":p,"QQQ_close":q,"source":"synthetic_test_fixture"})
                i+=1
            d+=timedelta(days=1)
        return out,{"provider":"synthetic_test_fixture","matched_sessions":len(out),
          "source":"synthetic_test_fixture_ONLY","price_basis":"synthetic_only","ticker":ticker}

    def fake_news(self,profile,ticker,from_day,to_day,max_news,*,use_proxy=False,log=print):
        out=[]
        samples=["growth improves strong strong results", "loss risk delay unexpected", "improves and gains market share",
                 "profitability improved and positive results", "risk of loss and delays",
                 "revenue growth improvement and strong gains", "uncertainty risk and losses", "great growth and improved efficiency"]
        for i,text in enumerate(samples):
            day=date(2026,10,12)+timedelta(days=3*i)
            out.append({"article_id":f"test-{ticker}-{i}","company":profile['name'],"source":"synthetic source",
             "source_type":"third_party_rss_auto_discovered_unverified",
             "title":f"{ticker} financial report test {i}",
             "url":f"https://example.org/{ticker.lower()}/test-{i}",
             "published_date":day.isoformat(),"published_time_quality":"synthetic_test_only",
             "text":("Company announces "+text+". ")*12,
             "text_chars":500,"retrieved_utc":"2026-11-05T12:00:00Z","synthetic":False,
             "extraction_strategy":"fixture","extraction_paragraphs":1})
        return out[:max_news],{"synthetic_test_fixture":True,"qualified_articles":len(out)}

    def test_three_companies_same_codepath(self):
        if not (v.INPUTS/"Loughran-McDonald_MasterDictionary_1993-2025.csv").exists():
            self.skipTest("Official LM csv required for full integration verification")
        with tempfile.TemporaryDirectory() as tmp:
            for ticker in ("NVDA","AAPL","GOOGL"):
                report=v.run_pipeline(v.validate_options(ticker=ticker,news_days=90,price_years=1,max_news=10,
                   price_mode="csv",local_llm=False),
                   log=lambda m:None,news_loader=self.fake_news,price_loader=self.fake_prices,
                   root_output=tmp,now_day=date(2026,11,6))
                self.assertEqual(report["ticker"],ticker)
                self.assertIn(report["status"],["complete","complete_with_warnings"])
                self.assertEqual(report["news"]["count"],8)
                self.assertGreater(report["prices"]["audit"]["matched_sessions"],20)
                self.assertTrue((Path(report["run_folder"])/"05_lm_labels.csv").exists())
                self.assertTrue((Path(report["run_folder"])/"07_prices.csv").exists())
                self.assertTrue((Path(report["run_folder"])/"research_report.json").exists())
                self.assertNotEqual(report["prices"]["audit"]["provider"],"yahoo_yfinance")


if __name__=="__main__":unittest.main()
