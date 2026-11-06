"""Synthetic tests for auditable research alignment, not real market findings."""
from __future__ import annotations
import unittest

from news2market.research import integration as mod


def row(name="filing",day="2026-01-05",ticker="NVDA", polarity="0.5",hits="5",form="8-K"):
    return {"article_id":name,"ticker":ticker,"form":form,"source_type":"sec_filing_primary_document",
            "published_date":day,"eligible_for_text_measurement":"True","text_quality":"complete_body",
            "text_truncated":"False","lm_text_truncated":"False","lm_polarity":polarity,
            "lm_polarity_hits":hits,"source":"SEC EDGAR","url":"https://www.sec.gov/Archives/example/"+name}


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.prices=[{"date":d,"NVDA_close":a,"QQQ_close":b} for d,a,b in [
            ("2026-01-05",100,100),("2026-01-06",110,101),("2026-01-07",121,102),
            ("2026-01-08",120,103),("2026-01-09",130,104),("2026-01-12",140,105),
            ("2026-01-13",150,106)]]

    def test_waits_until_close_after_document_date(self):
        e,a=mod.align_features_with_prices([row()],self.prices,"NVDA")
        self.assertEqual(e[0]["signal_close_date"],"2026-01-06")
        self.assertEqual(e[0]["outcome_date_1d"],"2026-01-07")
        self.assertAlmostEqual(e[0]["relative_return_1d"],121/110-102/101,8)
        self.assertEqual(a["unique_signal_days"],1)

    def test_missing_date_and_issuer_rejected(self):
        r=[row("bad_ticker",ticker="AAPL"),row("bad_date",day="unknown"),row()]
        e,a=mod.align_features_with_prices(r,self.prices,"NVDA")
        self.assertEqual(len(e),1)
        self.assertEqual(a["exclusion_reasons"]["ticker_mismatch"],1)
        self.assertEqual(a["exclusion_reasons"]["invalid_document_date"],1)

    def test_truncated_or_unscored_never_used(self):
        a=row("a");a["text_truncated"]="True"
        b=row("b");b["eligible_for_text_measurement"]="False"
        c=row("c");c["lm_text_truncated"]="True"
        e,quality=mod.align_features_with_prices([a,b,c,row("d")],self.prices,"NVDA")
        self.assertEqual(len(e),1)
        self.assertEqual(quality["excluded_records"],3)

    def test_low_hit_balanced_is_not_buy(self):
        e,a=mod.align_features_with_prices([row(hits="2",polarity="0")],self.prices,"NVDA")
        self.assertEqual(e[0]["lexical_tone"],"insufficient_lexicon_evidence")
        self.assertEqual(a["insufficient_evidence_events"],1)

    def test_no_future_return_and_missing_three_five_days(self):
        e,a=mod.align_features_with_prices([row("late",day="2026-01-12"),row("future",day="2026-01-13")],self.prices,"NVDA")
        self.assertEqual(e,[])
        self.assertEqual(a["exclusion_reasons"]["no_later_market_outcome"],2)
        e,a=mod.align_features_with_prices([row("early",day="2026-01-09")],self.prices,"NVDA")
        self.assertEqual(e[0]["relative_return_1d"],round((150/140-106/105),10))
        self.assertEqual(e[0]["relative_return_3d"],"")

    def test_news_and_sec_source_groups_not_mixed(self):
        n=row("n");n["form"]="";n["source_type"]="third_party";n["lm_polarity"]="-0.2"
        e,a=mod.align_features_with_prices([row(),n],self.prices,"NVDA")
        self.assertEqual(a["source_groups"],{"SEC 8-K":1,"News":1})
        self.assertEqual({x["lexical_tone"] for x in e},{"negative_tone_not_sell_signal","positive_tone_not_buy_signal"})

    def test_duplicate_document_ids_rejected(self):
        e,a=mod.align_features_with_prices([row(),row()],self.prices,"NVDA")
        self.assertEqual(len(e),1)
        self.assertEqual(a["exclusion_reasons"]["duplicate_document_id_or_url"],1)

if __name__=="__main__": unittest.main()
