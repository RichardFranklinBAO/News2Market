"""Offline research-integrity regression tests; no live SEC or actual findings."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from news2market.research import sec,metrics,cli
from news2market.research.identity import classify,validate_rows

class QualityTests(unittest.TestCase):
    class Lex:
        sha256='fake-lexicon'
        def __init__(self):self.calls=[]
        def score(self,title,body,char_cap):
            self.calls.append((title,body))
            return {'lm_no_polarity_hits':False,'lm_positive_count':1,'lm_negative_count':0,
                    'lm_uncertainty_count':0,'lm_positive_per_1000':10.0,
                    'lm_negative_per_1000':0.0,'lm_uncertainty_per_1000':0.0,
                    'lm_polarity_hits':1,'lm_token_count':10,'score':1.0,'lm_text_truncated':False}

    def test_metadata_not_scored_even_with_sentiment_title(self):
        lex=self.Lex()
        feat,audit=metrics.measure_rows([{'article_id':'sec1','title':'Strong growth','text':'','text_status':'not_retrieved'}],lex)
        self.assertEqual(len(lex.calls),0)
        self.assertEqual(feat[0]['lm_polarity'],'')
        self.assertFalse(feat[0]['eligible_for_text_measurement'])
        self.assertEqual(audit['excluded_by_text_quality']['metadata_only'],1)

    def test_truncated_and_short_body_not_scored(self):
        lex=self.Lex()
        rows=[{'article_id':'a','title':'Great performance','text':'X '*150,'text_status':'truncated','text_truncated':True},
              {'article_id':'b','title':'Great performance','text':'big loss','text_status':'extracted'},
              {'article_id':'c','title':'Great performance','text':'X '*150,'text_status':'short_text'}]
        feat,audit=metrics.measure_rows(rows,lex)
        self.assertEqual(len(lex.calls),0)
        self.assertEqual(audit['eligible_complete_bodies'],0)
        self.assertTrue(all(x['lm_polarity']=='' for x in feat))

    def test_complete_body_scored_without_title(self):
        lex=self.Lex()
        feat,audit=metrics.measure_rows([{'article_id':'x','text':'growth and improved operating results '*6,'title':'positive',
                                         'text_status':'extracted','text_truncated':False}],lex)
        self.assertEqual(lex.calls[0][0],'')
        self.assertEqual(audit['eligible_complete_bodies'],1)
        self.assertEqual(feat[0]['lm_polarity'],1.0)

    def test_text_truncated_string_false_not_misinterpreted(self):
        x={'text':'Growth and investments expected to continue throughout the fiscal year, ' * 3,
           'text_status':'extracted','text_truncated':'False'}
        self.assertEqual(metrics.text_quality(x),'complete_body')
        x['text_truncated']='True'
        self.assertEqual(metrics.text_quality(x),'partial_or_truncated')

    def test_tfidf_ignores_metadata_and_truncated(self):
        rows=[{'article_id':'meta','title':'extraordinary success','text':'','text_status':'not_retrieved'},
              {'article_id':'full1','title':'IBM','text':'growth revenue investment '*9,'text_status':'extracted'},
              {'article_id':'full2','title':'IBM','text':'revenue constraints lending '*9,'text_status':'extracted'}]
        top,audit=metrics.tfidf_descriptives(rows)
        self.assertEqual(audit['documents'],2)
        self.assertTrue(all(z['article_id']!='meta' for z in top))

class IdentityTests(unittest.TestCase):
    def test_ticker_conflict_rejected(self):
        accepted,meta=validate_rows([{'article_id':'x','ticker':'AAPL','title':'NVIDIA profits'}],'NVDA')
        self.assertFalse(accepted)
        self.assertEqual(meta['rejected'],1)

    def test_cik_conflict_rejected(self):
        ok,evidence,reason=classify({'cik':'0000320193','title':'NVIDIA'},'NVDA')
        self.assertFalse(ok);self.assertEqual(evidence,'cik_conflict')

    def test_sec_url_conflict_rejected(self):
        ok,evidence,_=classify({'title':'Nvidia outlook','url':'https://www.sec.gov/Archives/edgar/data/320193/001/a.htm'},'NVDA')
        self.assertFalse(ok);self.assertEqual(evidence,'sec_url_cik_conflict')

    def test_not_silently_assign_unknown_company(self):
        a,b=validate_rows([{'title':'Tech stocks rebound','text':'A broad market event','url':'https://example.org/a'}],'AAPL')
        self.assertEqual(len(a),0);self.assertEqual(b['rejected'],1)

    def test_heuristic_title_must_be_disclosed(self):
        a,b=validate_rows([{'article_id':'a','title':'Nvidia releases chip','url':'https://example.org/a'}],'NVDA')
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]['company_identity_evidence'],'title_alias_heuristic')

    def test_apple_orchard_is_not_issuer(self):
        self.assertFalse(classify({'title':'Apple orchard grows for festival'},'AAPL')[0])

class SECBodyTests(unittest.TestCase):
    def _filing(self):
        return {'article_id':'SEC-test','url':'https://www.sec.gov/Archives/edgar/data/1045810/1/filing.htm',
                'title':'Form 8-K','text':'','text_status':'not_retrieved','text_truncated':False}

    def test_byte_truncation_never_extracted(self):
        f=self._filing()
        client=Mock()
        client.get.return_value=(b'<html><body>'+b'Investment risk and growth. '*15+b'</body></html>',
                {'sha256':'raw','bytes':500,'truncated':True,'content_type':'text/html'})
        rows,issues=sec.fetch_bodies(client,[f])
        self.assertEqual(rows[0]['text_status'],'truncated')
        self.assertEqual(metrics.text_quality(rows[0]),'partial_or_truncated')
        self.assertEqual(rows[0]['raw_response_sha256'],'raw')

    def test_char_truncation_never_extracted(self):
        f=self._filing()
        client=Mock()
        client.get.return_value=(b'<html><body>'+b'Risk information. '*200+b'</body></html>',
                {'sha256':'raw','bytes':3400,'truncated':False,'content_type':'text/html'})
        before=sec.MAX_TEXT_CHARS
        try:
            sec.MAX_TEXT_CHARS=100
            rows,_=sec.fetch_bodies(client,[f])
            self.assertEqual(rows[0]['text_status'],'truncated')
            self.assertEqual(len(rows[0]['text']),100)
        finally:sec.MAX_TEXT_CHARS=before

    def test_sec_429_stops_remaining_downloads(self):
        c=Mock()
        c.get.side_effect=sec.SecAccessError('SEC returned HTTP 429')
        f=self._filing();f2=dict(f,article_id='SEC-second')
        rows,issues=sec.fetch_bodies(c,[f,f2])
        self.assertEqual(c.get.call_count,1)
        self.assertEqual(rows[1]['text_status'],'not_attempted_after_access_limit')

    def test_sec_audit_counts_truncated(self):
        f=self._filing()
        f.update(text_status='truncated',text_truncated=True)
        report=cli._collection_quality([f])
        self.assertEqual(report['complete_bodies'],0)
        self.assertEqual(report['truncated_bodies'],1)

    def test_submissions_mismatched_cik_rejected(self):
        c=sec.SecClient('Researcher example@research.org',session=Mock())
        c.get=lambda *args,**kwargs: (json.dumps({'cik':320193,'filings':{'recent':{}}}).encode(),
                                      {'truncated':False})
        with self.assertRaisesRegex(sec.SecAccessError,'CIK'):
            c.submissions('1045810')

class CLIAuditIntegrationTests(unittest.TestCase):
    """Exercise the public research command using offline simulated SEC metadata."""
    def test_metadata_only_sec_command_creates_audit_without_lm(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            payload={'cik':1045810,'filings':{'recent':{
                'accessionNumber':['0001045810-26-000091'],
                'filingDate':['2026-10-18'],'form':['8-K'],
                'primaryDocument':['nvda-20261018.htm'],
                'acceptanceDateTime':['2026-10-18T16:22:00']}}}
            inp=t/'submissions.json';inp.write_text(json.dumps(payload))
            args=Namespace(ticker='NVDA',output_root=t/'out',
                start='2026-10-01',end='2026-11-05',max_filings=5,
                fetch_bodies=False,submissions_json=str(inp),news_csv=None,
                sec_user_agent=None,dictionary=t/'missing_lm.csv',no_tfidf=True)
            folder,audit=cli.command_sec(args)
            self.assertEqual(audit['sec_collection_quality']['selected'],1)
            self.assertEqual(audit['sec_collection_quality']['complete_bodies'],0)
            self.assertEqual(audit['research_scores']['status'],'no_eligible_complete_text_available')
            self.assertTrue((folder/'sec_collection_audit.json').exists())
            self.assertTrue((folder/'sec_data_quality_report.md').exists())
            report=json.loads((folder/'sec_collection_audit.json').read_text())
            self.assertEqual(report['source_mode'],'user_supplied_local_json')
            self.assertFalse(report['real_sec_access_verified_in_this_run'])
            self.assertEqual(report['text_status_counts']['not_retrieved'],1)

    def test_conflicting_submissions_cik_fails_and_keeps_failure_audit(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp); inp=t/'submissions.json'
            inp.write_text(json.dumps({'cik':320193,'filings':{'recent':{
                'accessionNumber':[],'filingDate':[],'form':[],'primaryDocument':[]}}}))
            args=Namespace(ticker='NVDA',output_root=t/'out',
                start='2026-10-01',end='2026-11-05',max_filings=5,
                fetch_bodies=False,submissions_json=str(inp),news_csv=None,
                sec_user_agent=None,dictionary=t/'missing_lm.csv',no_tfidf=True)
            with self.assertRaisesRegex(ValueError,'CIK conflicts'):
                cli.command_sec(args)
            folders=list((t/'out'/'NVDA'/'Research').glob('*'))
            self.assertEqual(len(folders),1)
            failure=json.loads((folders[0]/'sec_collection_audit.json').read_text())
            self.assertEqual(failure['status'],'failed_or_incomplete')


if __name__=='__main__': unittest.main()
