"""Offline tests: no API, no market download, no fake news labeled as real."""
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
from lm_dictionary import load_lm_dictionary
from nvidia_scraper import extract_article_text_with_audit, extract_archive_candidates
from signal_core import construct
from common import clean_text

def load_module(filename):
    spec=importlib.util.spec_from_file_location(filename.replace('.py',''),ROOT/'Scripts'/filename)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class News2MarketTests(unittest.TestCase):
    def test_company_resolver(self):
        mod=load_module('00_resolve_company.py')
        obj=mod.resolve_from_mapping('AAPL',{'0':{'ticker':'AAPL','title':'Apple Inc.','cik_str':320193}})
        self.assertEqual(obj['cik'],'0000320193')
        with self.assertRaises(ValueError): mod.resolve_from_mapping('NVDA',{'0':{'ticker':'AAPL','title':'Apple Inc.','cik_str':320193}})

    def test_html_extractor(self):
        html='<html><body><article class="card"><p>Short.</p></article><main><section><p>'+('A financial announcement paragraph about a new customer. '*4)+'</p></section></main></body></html>'
        text,info=extract_article_text_with_audit(html)
        self.assertIn('financial announcement',text)
        self.assertGreaterEqual(info['paragraphs'],1)

    def test_archive_parsing(self):
        html='<html><body><p>November 4, 2026</p><h3><a href="/news/valid">New NVIDIA Release</a></h3></body></html>'
        result=extract_archive_candidates(html,'https://nvidianews.nvidia.com/news?c=21926')
        self.assertEqual(result[0]['published_date'],'2026-11-04')
        self.assertTrue(result[0]['url'].startswith('https://nvidianews.nvidia.com/news/'))

    def test_lm_full_token_not_substring(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'dictionary.csv'
            with f.open('w',newline='',encoding='utf-8') as h:
                w=csv.writer(h);w.writerow(['Word','Positive','Negative','Uncertainty','Litigious','Strong_Modal','Weak_Modal','Constraining'])
                w.writerow(['GROWTH',2011,0,0,0,0,0,0]);w.writerow(['LOSS',0,2011,0,0,0,0,0]);w.writerow(['UNCERTAIN',0,0,2011,0,0,0,0]);w.writerow(['DELAY',0,-2018,0,0,0,0,0])
            lex=load_lm_dictionary(f,min_entries=1)
            record=lex.score('GROWTH','Growth losses LOSS uncertain delay',1000)
            self.assertEqual(record['lm_positive_count'],2)
            self.assertEqual(record['lm_negative_count'],1)
            self.assertEqual(record['lm_uncertainty_count'],1)
            self.assertAlmostEqual(record['score'],1/3,5)

    def test_prices_parse_and_reject_duplicates(self):
        mod=load_module('07_get_prices.py')
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'NVDA.csv'
            f.write_text('Date,Close/Last\n2026-10-01,$120.33\n2026-10-02,$121.40\n')
            rows,kind=mod.parse_price_csv(f)
            self.assertEqual(kind,'raw_close_unadjusted')
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['date'],'2026-10-01')
            f.write_text('Date,Close/Last\n2026-10-01,$120.33\n2026-10-01,$121.40\n')
            with self.assertRaises(ValueError):mod.parse_price_csv(f)

    def test_nasdaq_mmddyyyy_and_currency(self):
        mod=load_module('07_get_prices.py')
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'NVDA.csv'
            f.write_text('Date,Close/Last,Volume,Open,High,Low\n11/04/2026,$200.13,149033300,$203.50,$206.79,$199.68\n11/03/2026,$206.69,91943390,$207.96,$209.14,$205.93\n')
            rows,kind=mod.parse_price_csv(f)
            self.assertEqual(kind,'raw_close_unadjusted')
            self.assertEqual(rows,[{'date':'2026-11-03','close':206.69},{'date':'2026-11-04','close':200.13}])
            f.write_text('Date,Close/Last\n11/32/2026,$200\n')
            with self.assertRaises(ValueError):mod.parse_price_csv(f)

    def test_five_year_csv_imports_and_matches(self):
        mod=load_module('07_get_prices.py')
        asset_path=ROOT/'Inputs'/'prices'/'NVDA.csv'
        benchmark_path=ROOT/'Inputs'/'prices'/'QQQ.csv'
        if not (asset_path.exists() and benchmark_path.exists()):
            self.skipTest('Optional five-year proprietary local price CSVs not bundled in public repository')
        a,ka=mod.parse_price_csv(asset_path)
        b,kb=mod.parse_price_csv(benchmark_path)
        paired=mod.combine_prices(a,b,'NVDA','QQQ')
        self.assertEqual(len(a),1254)
        self.assertEqual(len(b),1254)
        self.assertEqual(len(paired),1254)
        self.assertEqual(paired[0]['date'],'2021-11-05')
        self.assertEqual(paired[-1]['date'],'2026-11-04')
        self.assertEqual(ka,'raw_close_unadjusted')
        self.assertEqual(kb,'raw_close_unadjusted')
        prices={x['date']:x['NVDA_close'] for x in paired}
        # 10-for-1 split has been reflected on earlier price scale.
        self.assertLess(abs(prices['2024-06-10']/prices['2024-06-07']-1),0.05)

    def test_align_conservative_date_only(self):
        prices=[{'date':f'2026-10-0{j}','NVDA_close':100+j,'QQQ_close':100+j/2} for j in range(1,7)]
        labels=[{'article_id':'x','published_date':'2026-10-01','score':'0.5','event_type':'Earnings',
                 'source':'TEST','label_method':'lm','lm_positive_per_1000':'1','lm_negative_per_1000':'0','lm_uncertainty_per_1000':'0'}]
        daily,matched,failed=construct(labels,prices)
        self.assertEqual(daily[0]['signal_date'],'2026-10-02')
        self.assertEqual(daily[0]['outcome_date'],'2026-10-03')
        self.assertEqual(len(failed),0)

    def test_sec_filings_are_not_news_links(self):
        mod=load_module('01_discover_sources.py')
        subj={'filings':{'recent':{'form':['8-K','4','10-Q'], 'filingDate':['2026-10-07','2026-10-08','2026-10-09'],
              'primaryDocument':['a.htm','b.htm','c.htm'],'accessionNumber':['0000000000-26-000001','0000000000-26-000002','0000000000-26-000003']}}}
        rows=mod.make_sec_candidates(subj,'2026-10-01','2026-10-31','0000320193')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['source_type']=='first_party_filing' for r in rows))

    def test_manifest_prevents_fake_success(self):
        text=(ROOT/'run_all.py').read_text()
        self.assertIn("status('FAILED',False",text)
        self.assertIn('collect-only',text)
        self.assertNotIn('yfinance', (ROOT/'Scripts'/'07_get_prices.py').read_text())


    def test_nlp_footer_preserves_original(self):
        mod=load_module('11_prepare_text.py')
        row={'text':'A financial statement announces sales growth. '*10+' About NVIDIA NVIDIA is the world leader. Safe Harbor risk risk risk.',
             'source_type':'first_party_press_release','url':'https://nvidianews.nvidia.com/news/example'}
        trimmed=mod.trim_boilerplate(row)
        self.assertIn('Safe Harbor',trimmed['text'])
        self.assertNotIn('Safe Harbor',trimmed['narrative_text'])
        self.assertTrue(trimmed['boilerplate_removed_chars']>0)

    def test_local_model_evidence_id_and_score_rejection(self):
        mod=load_module('12_local_llm_labels.py')
        original={'title':'NVIDIA announces annual revenue results',
                  'narrative_text':'Revenue increased by 12 percent this quarter.'}
        candidates=['Revenue increased by 12 percent this quarter.']
        obj={'direction':'Positive','sentiment_score':0.6,'event_type':'Earnings',
             'evidence_id':1,'economic_channel':'Revenue_Demand'}
        score,valid,reason,quote,eid=mod.validate(obj,original,candidates)
        self.assertTrue(valid)
        self.assertEqual(reason,'')
        self.assertEqual(quote,candidates[0])
        self.assertAlmostEqual(score,0.6)
        self.assertEqual(eid,1)
        _,valid,reason,_,_=mod.validate({**obj,'evidence_id':0},original,candidates)
        self.assertFalse(valid)
        self.assertTrue(reason)
        with self.assertRaises(ValueError):
            mod.validate({**obj,'sentiment_score':4},original,candidates)

    def test_price_paired_synthetic_fixture(self):
        mod=load_module('07_get_prices.py')
        a=[{'date':'2026-01-02','close':100},{'date':'2026-01-05','close':105},
           {'date':'2026-01-06','close':102}]
        b=[{'date':'2026-01-02','close':50},{'date':'2026-01-05','close':51},
           {'date':'2026-01-06','close':52}]
        paired=mod.combine_prices(a,b,'NVDA','QQQ')
        self.assertEqual(len(paired),3)
        self.assertEqual(paired[-1]['NVDA_close'],102)

    def test_auto_rss_discovery_offline(self):
        mod=load_module('15_auto_external_news.py')
        raw=b'<rss><channel><item><title>NVIDIA expands AI infrastructure</title><link>https://example.org/news/nvda</link><pubDate>Thu, 05 Nov 2026 12:00:00 GMT</pubDate><description>NVDA demand</description></item></channel></rss>'
        rows=mod.parse_feed(raw,'Example_Feed')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['published_date'],'2026-11-05')
        self.assertTrue(mod.is_relevant(rows[0]['title'],rows[0]['summary'],'NVIDIA'))
        self.assertFalse(mod.is_relevant('Different company','Different product','NVIDIA'))
        self.assertTrue(mod.candidate_extraction_note('https://news.google.com/rss/articles/abc'))

    def test_external_bridge_rejects_bad_or_duplicate_rows(self):
        mod=load_module('16_auto_news_research.py')
        baseline={'article_id':'abc','company':'NVDA','source_type':'third_party_rss_auto_discovered_unverified',
                  'url':'https://example.org/news/article','text':'A'*400,
                  'published_date':'2026-11-05','synthetic':'False',
                  'published_time_quality':'page_meta_date_agrees_with_RSS_date'}
        eligible,excluded=mod.select_articles([baseline,dict(baseline)],{'date_window':['2026-10-06','2026-11-05']},'NVDA')
        self.assertEqual(len(eligible),1)
        self.assertEqual(len(excluded),1)
        self.assertIn('duplicate_article',excluded[0]['reasons'])

    def test_external_web_relevance_and_local_url_block(self):
        mod=load_module('03b_scrape_external.py')
        self.assertTrue(mod.is_relevant_title('NVIDIA increases AI supply','NVIDIA CORPORATION','NVDA'))
        self.assertFalse(mod.is_relevant_title('Microsoft announces new Azure servers','NVIDIA CORPORATION','NVDA'))
        self.assertFalse(mod.public_http_url('http://127.0.0.1:8080/private'))
        self.assertFalse(mod.public_http_url('https://127.0.0.1/private'))

    def test_no_paid_model_or_cloud_endpoint(self):
        text=(ROOT/'Scripts'/'12_local_llm_labels.py').read_text(encoding='utf-8')
        self.assertIn('http://127.0.0.1:11434',text)
        self.assertIn('Cloud models are prohibited',text)
        self.assertNotIn('api.openai.com',text)

if __name__=='__main__':unittest.main()
