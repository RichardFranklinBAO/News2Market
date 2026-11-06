"""Offline regression tests; synthetic SEC responses and texts are NOT research evidence."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from news2market.research import sec,metrics,evaluation


class SECProtocolTests(unittest.TestCase):
    def test_company_filings_filter_and_url(self):
        payload={'filings':{'recent':{
          'accessionNumber':['0001045810-26-000123','0001045810-26-000124','0001045810-26-000125','0001045810-26-000123'],
          'filingDate':['2026-10-20','2026-10-21','2026-10-22','2026-10-22'],
          'form':['8-K','10-Q','4','8-K'],
          'primaryDocument':['nvda-8k.htm','nvda-10q.htm','bad.htm','nvda-x.htm'],
          'acceptanceDateTime':['2026-10-20T18:00:00','2026-10-21T15:10:00','','']}}}
        r=sec.select_filings(payload,'0001045810','2026-10-01','2026-11-01')
        self.assertEqual(len(r),2)
        self.assertEqual(r[0]['form'],'10-Q')
        self.assertTrue(r[0]['url'].startswith('https://www.sec.gov/Archives/edgar/data/1045810/'))
        self.assertIn('acceptance',r[0]['published_time_quality'])

    def test_reject_unsafe_paths(self):
        for value in ('../private.html','a/b.htm','a?x.html','..htm'):
            with self.assertRaises(ValueError):sec._filing_url('1045810','0001045810-26-000001',value)
        with self.assertRaises(ValueError):sec._filing_url('1045810','unexpected','hello.htm')

    def test_agent_required_and_hosts_restricted(self):
        with self.assertRaises(ValueError):sec.SecClient('News2Market')
        client=sec.SecClient('Independent Research research@example.com',session=Mock(),delay=.5)
        with self.assertRaises(ValueError):client.get('https://example.com/anything')
        self.assertEqual(client.requests_made,0)

    def test_rate_limited_once_without_retry(self):
        response=Mock(status_code=429)
        session=Mock();session.get.return_value=response
        client=sec.SecClient('Independent Research research@example.com',session=session)
        with self.assertRaisesRegex(sec.SecAccessError,'429'):
            client.get('https://data.sec.gov/submissions/CIK0001045810.json')
        self.assertEqual(session.get.call_count,1)
        response.close.assert_called_once()

    def test_filing_html_cleaning(self):
        raw=b'<html><head><title>Ignore</title></head><body><p>Material risk</p><script>secret()</script><p>cash flows</p></body></html>'
        text=sec.html_to_text(raw,'text/html')
        self.assertEqual(text,'Material risk cash flows')
        with self.assertRaises(ValueError):sec.html_to_text(b'%PDF-1.7', 'application/pdf')

    def test_future_form_and_range_rejected(self):
        x={'filings':{'recent':{'accessionNumber':[],'filingDate':[],'form':[],'primaryDocument':[]}}}
        with self.assertRaises(ValueError):sec.select_filings(x,'1045810','2026-12-01','2026-01-01')
        with self.assertRaises(ValueError):sec.select_filings(x,'1045810','2026-01-01','2026-12-01',forms=['S-1'])


class TextMeasurementTests(unittest.TestCase):
    def test_normalize_and_deduplicate(self):
        rows=[{'article_id':'a','url':'https://sec.gov/a','title':'Title','text':'good bad'},
              {'article_id':'b','url':'https://sec.gov/a/','title':'Copy','text':'good bad'},
              {'article_id':'c','url':'https://sec.gov/c','title':'Another','body':'bad good'}]
        clean,excluded=metrics.canonical_rows(rows)
        self.assertEqual(len(clean),2)
        self.assertEqual(len(excluded),1)
        self.assertEqual(clean[1]['text'],'bad good')

    def test_measure_missing_polarity_stays_missing(self):
        class FakeLex:
            sha256='test-only'
            def score(self,title,body,char_cap):
                missed=not ('growth' in body)
                return {'lm_no_polarity_hits':missed,'lm_positive_count':int(not missed),
                        'lm_negative_count':0,'lm_uncertainty_count':0,
                        'lm_positive_per_1000':10.0,'lm_negative_per_1000':0.0,'lm_uncertainty_per_1000':0.0,
                        'lm_polarity_hits':int(not missed),'lm_token_count':10,'score':1.0 if not missed else 0.0,
                        'lm_text_truncated':False}
        rows=[{'article_id':'a','text':'This is purely factual and contains no category hit. The document has several further descriptive sentences without anything resembling a change in company operating conditions. '},
              {'article_id':'b','text':'strong growth may be expected later. The company described operational execution, new capacity plans, investment risks and its continuing financial disclosure work across the quarter. '}]
        out,audit=metrics.measure_rows(rows,FakeLex())
        self.assertEqual(out[0]['lm_polarity'],'')
        self.assertEqual(out[1]['lm_polarity'],1.0)
        self.assertEqual(audit['missing_lm_polarity'],1)

    def test_tfidf_is_explicitly_descriptive(self):
        rows=[{'article_id':'a','title':'Battery production','text':'battery production grows production ' * 8},
              {'article_id':'b','title':'Investment constraints','text':'investment constraints refinancing ' * 8}]
        got,audit=metrics.tfidf_descriptives(rows)
        self.assertFalse(audit['tfidf_is_sentiment'])
        if audit['status'].startswith('descriptive'):
            self.assertGreater(len(got),0)
        else:self.assertEqual(audit['status'],'sklearn_not_installed')

    def test_large_sec_csv_body_is_read_without_default_field_limit(self):
        # Regression: 10-Q/10-K text in a single CSV cell can exceed 131072.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sec_corpus.csv'
            original_body='Revenue and operations. ' * 8000
            self.assertGreater(len(original_body),131072)
            self.assertLess(len(original_body),sec.MAX_TEXT_CHARS)
            with p.open('w',encoding='utf-8',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=['article_id','ticker','text'])
                writer.writeheader()
                writer.writerow({'article_id':'sec-large','ticker':'NVDA','text':original_body})
            loaded=metrics.read_articles_csv(p)
            self.assertEqual(len(loaded),1)
            self.assertEqual(loaded[0]['text'],original_body)
            self.assertEqual(metrics.text_quality(loaded[0]),'complete_body')

    def test_no_arbitrary_input_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv';p.write_text('article_id,title\na,Test\n')
            with self.assertRaisesRegex(ValueError,'text'):
                metrics.read_articles_csv(p)


class HumanEvaluationTests(unittest.TestCase):
    def test_reject_ai_assisted_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'labels.csv'
            p.write_text('article_id,label,label_source\na,positive,AI_assisted\n')
            with self.assertRaises(evaluation.EvaluationNotSupported):
                evaluation.read_human_labels(p)

    def test_reject_tiny_datasets(self):
        data=[{'article_id':f'a{i}','published_date':f'2026-10-{i+1:02d}',
               'text':('strong market growth and investment ')*5} for i in range(6)]
        labels={r['article_id']:'positive' for r in data}
        with self.assertRaises(evaluation.EvaluationNotSupported):
            evaluation.chrono_split(data,labels)

    def test_temporal_split_and_holdout(self):
        from datetime import date,timedelta
        base=date(2026,1,1)
        rows=[];labs={}
        for i in range(45):
            aid=f'a{i}';label=['positive','neutral','negative'][i%3]
            rows.append({'article_id':aid,'published_date':(base+timedelta(days=i)).isoformat(),
                        'title':f'{label} market report {i}',
                        'text':f'Company report number {i} about {label} operations and financial capital projects'});
            labs[aid]=label
        train,test=evaluation.chrono_split(rows,labs)
        self.assertLess(max(x[0] for x in train),min(x[0] for x in test))
        self.assertGreaterEqual(len(test),8)

if __name__=='__main__':unittest.main()
