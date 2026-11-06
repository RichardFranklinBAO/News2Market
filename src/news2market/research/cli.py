"""Research CLI: SEC data + LM/TF-IDF measurement + human-label OOS checks.

Run: python -m news2market research --help
The original dashboard remains: python -m news2market --web
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from . import sec
from .identity import validate_rows
from .metrics import canonical_rows, load_official_lm, measure_rows,tfidf_descriptives,read_articles_csv,write_rows
from .evaluation import benchmark_human_labels,read_human_labels,EvaluationNotSupported

ROOT=Path(__file__).resolve().parents[3]
LM_PATH=ROOT/'inputs'/'Loughran-McDonald_MasterDictionary_1993-2025.csv'


def write_json(path,contents):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(contents,indent=2,ensure_ascii=False,default=str),encoding='utf-8')


def run_folder(ticker,output_root=None):
    base=Path(output_root) if output_root is not None else ROOT/'Results'
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target=base/ticker/'Research'/name
    target.mkdir(parents=True,exist_ok=False)
    return target


def _company(ticker):
    from news2market.core import COMPANIES
    sym=ticker.upper()
    if sym not in COMPANIES:raise ValueError('Choose NVDA, AAPL or GOOGL')
    return sym,COMPANIES[sym]


def _score_corpus(rows,folder,dictionary,include_tfidf=True):
    lex=load_official_lm(dictionary)
    clean,dropped=canonical_rows(rows)
    feats,measurement=measure_rows(clean,lex)
    write_rows(folder/'corpus_local.csv',clean,fields=['article_id','ticker','published_date','accepted_datetime_raw',
        'published_time_quality','source','source_type','form','accession','url','title','text','text_status',
        'text_sha256','text_truncated','company_identity_evidence'])
    write_rows(folder/'research_features.csv',feats,fields=['article_id','ticker','published_date',
        'accepted_datetime_raw','published_time_quality','source','source_type','form','url','title','text_status',
        'text_sha256','text_chars','text_truncated','text_quality','eligible_for_text_measurement',
        'company_identity_evidence','lm_token_count','lm_positive_count','lm_negative_count',
        'lm_uncertainty_count','lm_positive_per_1000','lm_negative_per_1000','lm_uncertainty_per_1000',
        'lm_polarity_hits','lm_polarity','lm_text_truncated'])
    if include_tfidf:
        top,diag=tfidf_descriptives(clean)
        write_rows(folder/'tfidf_top_terms.csv',top,fields=['article_id','term','tfidf_weight'])
    else:diag={'status':'disabled'}
    return {'measurement':measurement,'tfidf':diag,'deduplicated':len(dropped),
            'excluded':dropped[:40], 'output_records':len(feats),
            'text_scored_records':measurement['eligible_complete_bodies'],
            'warning':'Outputs are research measurements, not verified financial surprises or stock-return predictions'}


def _collection_quality(rows,client=None):
    from collections import Counter
    statuses=Counter(str(r.get('text_status') or 'unknown') for r in rows)
    lengths=[len(str(r.get('text') or '')) for r in rows if str(r.get('text_status'))=='extracted']
    truncated=sum(bool(r.get('text_truncated')) for r in rows)
    by_form=dict(Counter(str(r.get('form') or '') for r in rows))
    return {'selected':len(rows),'by_form':by_form,'text_status_counts':dict(statuses),
            'complete_bodies':statuses.get('extracted',0),
            'truncated_bodies':truncated,
            'missing_or_unusable_bodies':len(rows)-statuses.get('extracted',0),
            'complete_body_rate':round(statuses.get('extracted',0)/len(rows),4) if rows else None,
            'complete_body_chars':{'min':min(lengths) if lengths else None,
              'max':max(lengths) if lengths else None,
              'mean':round(sum(lengths)/len(lengths),1) if lengths else None},
            'acceptance_timestamps_present':sum(bool(str(r.get('accepted_datetime_raw') or '').strip()) for r in rows),
            'sec_http_requests':getattr(client,'requests_made',0),
            'audit_limitation':'The counts document retrieval quality, not economic relevance or first market availability'}


def _write_sec_quality_report(folder,quality):
    """Human-readable retrieval audit; NOT an empirical research result."""
    counts=quality.get('text_status_counts',{})
    lines=['# SEC Collection Data-Quality Report','',
        'This report summarizes **this run only**. It does not validate market information timing, trading returns, or all past SEC filings.','',
        f"- Issuer: {quality.get('ticker')} (CIK {quality.get('cik')})",
        f"- Source: {quality.get('source_mode')}",
        f"- Selected filings: {quality.get('selected',0)}",
        f"- Complete, scored-eligible bodies: {quality.get('complete_bodies',0)}",
        f"- Truncated bodies (excluded from measurement): {quality.get('truncated_bodies',0)}",
        f"- Missing, short, blocked, or unsupported bodies: {quality.get('missing_or_unusable_bodies',0)}",
        f"- Requests made: {quality.get('sec_http_requests',0)}",
        f"- Acceptance timestamp fields present: {quality.get('acceptance_timestamps_present',0)}",
        '', '## Extraction status breakdown','']
    lines.extend(f'- `{k}`: {v}' for k,v in sorted(counts.items()))
    lines.extend(['', '## Interpretation', '',
        'Truncated and metadata-only records are retained for provenance, but must not contribute LM or TF-IDF features.',
        'A valid SEC acceptance field does not, by itself, establish first availability to market participants.',
        'The default local 1.5 MB response cap and 240,000-character text cap can exclude large 10-K filings.',
        'For live verification, use small 8-K batches and record any SEC 403/429 without retrying or circumventing it.',''])
    (folder/'sec_data_quality_report.md').write_text('\n'.join(lines),encoding='utf-8')

def command_sec(args):
    ticker,company=_company(args.ticker)
    folder=run_folder(ticker,args.output_root)
    audit={'ticker':ticker,'cik':company['cik'],'source':'SEC EDGAR / data.sec.gov submissions API',
           'data_source':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',
           'study_window':{'start':args.start,'end':args.end},'forms':['8-K','10-Q','10-K'],
           'sec_user_agent_declared':False,'body_fetch_requested':bool(args.fetch_bodies),
           'past_filings_completeness':'recent submissions arrays only; older archive shards not downloaded',
           'acceptance_time_warning':'SEC acceptance fields are recorded verbatim; market-availability timestamps not independently verified',
           'limits':['no causal inference','no automatic Nasdaq download','source HTML may contain boilerplate or attachments not extracted']}
    try:
        if args.submissions_json:
            src=Path(args.submissions_json)
            if src.stat().st_size > 20_000_000:raise ValueError('SEC submissions fixture >20MB')
            submissions=json.loads(src.read_text(encoding='utf-8'))
            audit['submissions_source']='user_supplied_local_json'
            audit['submissions_sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
        else:
            agent=args.sec_user_agent or os.environ.get('N2M_SEC_USER_AGENT','')
            client=sec.SecClient(agent)
            audit['sec_user_agent_declared']=True
            submissions=client.submissions(company['cik'])
            audit['submissions_source']='data.sec.gov API'
        payload_cik=submissions.get('cik')
        if payload_cik is not None and str(int(payload_cik))!=str(int(company['cik'])):
            raise ValueError('SEC submissions JSON issuer CIK conflicts with selected ticker')
        audit['submissions_cik_status']='matched' if payload_cik is not None else 'not_supplied_cannot_verify'
        rows=sec.select_filings(submissions,company['cik'],args.start,args.end,limit=args.max_filings)
        for row in rows:
            row['ticker']=ticker
            row['company_identity_evidence']='sec_submissions_cik_'+audit['submissions_cik_status']
        audit['disclosures_selected']=len(rows)
        if args.fetch_bodies and rows:
            agent=args.sec_user_agent or os.environ.get('N2M_SEC_USER_AGENT','')
            if not sec.valid_agent(agent):
                raise ValueError('Reading SEC filing bodies requires a declared SEC user agent with a contact email')
            if 'client' not in locals():client=sec.SecClient(agent)
            audit['sec_user_agent_declared']=True
            rows,issues=sec.fetch_bodies(client,rows)
            audit['download_issues']=issues
            audit['body_successes']=sum(x.get('text_status')=='extracted' for x in rows)
        else:
            audit['body_successes']=0
        # Header-only output is still useful when access to body text is disabled.
        write_rows(folder/'sec_filings.csv',rows,fields=['article_id','ticker','cik','form','accession',
          'published_date','accepted_datetime_raw','published_time_quality','source','source_type','url',
          'title','text_status','text_truncated','text_sha256','downloaded_bytes',
          'raw_response_sha256','response_truncated','extracted_chars_before_cap','company_identity_evidence'])
        quality=_collection_quality(rows,locals().get('client'))
        quality.update({'ticker':ticker,'cik':company['cik'],
                        'source':'SEC EDGAR','source_mode':audit['submissions_source'],
                        'filing_date_range':audit['study_window'],
                        'body_fetch_requested':bool(args.fetch_bodies),
                        'real_sec_access_verified_in_this_run':audit['submissions_source']=='data.sec.gov API',
                        'submissions_cik_status':audit['submissions_cik_status']})
        write_json(folder/'sec_collection_audit.json',quality)
        _write_sec_quality_report(folder,quality)
        audit['sec_collection_quality']=quality
        if args.news_csv:
            additional,identity=validate_rows(read_articles_csv(args.news_csv),ticker)
            audit['additional_news_identity_audit']=identity
            rows.extend(additional)
            audit['additional_local_news']=len(additional)
            audit['news_csv_sha256']=hashlib.sha256(Path(args.news_csv).read_bytes()).hexdigest()
        from .metrics import text_quality
        if any(text_quality(r)=='complete_body' for r in rows):
            audit['research_scores']=_score_corpus(rows,folder,args.dictionary,not args.no_tfidf)
        else:
            audit['research_scores']={'status':'no_eligible_complete_text_available',
                'how_to_proceed':'Add --fetch-bodies with N2M_SEC_USER_AGENT or --news-csv with verified saved articles; truncated text is excluded'}
        audit['status']='completed_with_limitations'
    except Exception as e:
        audit['status']='failed'
        audit['error']=f'{type(e).__name__}: {str(e)[:400]}'
        write_json(folder/'research_audit.json',audit)
        if not (folder/'sec_collection_audit.json').exists():
            write_json(folder/'sec_collection_audit.json',{'status':'failed_or_incomplete',
                'ticker':ticker,'error':audit['error'],'real_sec_access_verified':False})
        raise
    write_json(folder/'research_audit.json',audit)
    return folder,audit


def command_measure(args):
    ticker,_=_company(args.ticker)
    folder=run_folder(ticker,args.output_root)
    try:
        original=[];hashes={}
        for inp in args.input_csv:
            p=Path(inp)
            original.extend(read_articles_csv(p))
            hashes[str(p.name)]=hashlib.sha256(p.read_bytes()).hexdigest()
        accepted,identity=validate_rows(original,ticker)
        if not accepted:
            write_json(folder/'identity_audit.json',identity)
            raise ValueError('No input rows have acceptable issuer identity; see identity_audit.json')
        write_json(folder/'identity_audit.json',identity)
        from .metrics import text_quality
        if not any(text_quality(r)=='complete_body' for r in accepted):
            raise ValueError('No complete article bodies available; metadata/partial text cannot be scored')
        results=_score_corpus(accepted,folder,args.dictionary,not args.no_tfidf)
        audit={'status':'complete','ticker':ticker,'inputs_sha256':hashes,'identity':identity,'outputs':results,
            'limitations':['No human-valid sentiment labels are inferred by this command',
                           'TF-IDF is a text representation, not an economic-shock measure',
                           'XLex transformer/SHAP training was not run']}
        write_json(folder/'research_audit.json',audit)
        return folder,audit
    except Exception as e:
        write_json(folder/'research_audit.json',{'status':'failed','error':f'{type(e).__name__}: {e}'})
        raise


def command_benchmark(args):
    ticker,_=_company(args.ticker)
    folder=run_folder(ticker,args.output_root)
    try:
        raw=read_articles_csv(args.corpus_csv)
        verified,identity=validate_rows(raw,ticker)
        if not verified:
            write_json(folder/'identity_audit.json',identity)
            raise ValueError('Benchmark has no issuer-verified corpus rows')
        write_json(folder/'identity_audit.json',identity)
        data,_=canonical_rows(verified)
        from .metrics import text_quality
        data=[r for r in data if text_quality(r)=='complete_body']
        labels=read_human_labels(args.labels_csv)
        lex=load_official_lm(args.dictionary)
        result=benchmark_human_labels(data,labels,lex)
        audit={'status':'complete','ticker':ticker,'result':result,
               'corpus_sha256':hashlib.sha256(Path(args.corpus_csv).read_bytes()).hexdigest(),
               'labels_sha256':hashlib.sha256(Path(args.labels_csv).read_bytes()).hexdigest(),
               'identity':identity,
               'note':'Human labels are user asserted and have not been independently checked by the tool'}
        write_json(folder/'human_label_benchmark.json',audit)
        return folder,audit
    except Exception as e:
        write_json(folder/'human_label_benchmark.json',{'status':'not_estimated',
                  'reason':f'{type(e).__name__}: {str(e)[:400]}'})
        raise


def command_market(args):
    """Join independently measured news/SEC LM features with verified Nasdaq/QQQ prices.

    This returns descriptive textual tone and later relative market outcomes, not
    trading instructions, a calibrated return forecast, or causal identification.
    """
    ticker,_=_company(args.ticker)
    folder=run_folder(ticker,args.output_root)
    try:
        from .integration import run_market_integration
        summary=run_market_integration(ticker,args.features_csv,folder,
            min_directional_hits=args.min_directional_hits)
        audit={'status':'descriptive_only','ticker':ticker,'aligned_events':summary['aligned_events'],
               'market_assessment':summary,
               'limitations':['Textual tone is not a Buy/Sell order or a validated prediction',
                              'Market time of first information availability is not verified']}
        write_json(folder/'research_audit.json',audit)
        return folder,audit
    except Exception as exc:
        write_json(folder/'research_audit.json',{'status':'failed',
            'error':f'{type(exc).__name__}: {str(exc)[:400]}'})
        raise


def main(argv=None):
    p=argparse.ArgumentParser(prog='python -m news2market research',
        description='Auditable SEC filings, LM/TF-IDF features and held-out independent-label checks')
    sub=p.add_subparsers(dest='action',required=True)
    secp=sub.add_parser('sec',help='Collect selected-company 8-K/10-Q/10-K metadata, optional filing text and LM features')
    secp.add_argument('--ticker',required=True,choices=['NVDA','AAPL','GOOGL'])
    secp.add_argument('--start',required=True,help='Inclusive YYYY-MM-DD filing date')
    secp.add_argument('--end',required=True,help='Inclusive YYYY-MM-DD filing date')
    secp.add_argument('--max-filings',type=int,default=10)
    secp.add_argument('--fetch-bodies',action='store_true',help='Retrieve permitted primary HTML documents, not exhibits')
    secp.add_argument('--sec-user-agent',default=None,help='Your name and contact email, or N2M_SEC_USER_AGENT environment variable')
    secp.add_argument('--submissions-json',help='Offline SEC submissions snapshot; no API request unless --fetch-bodies')
    secp.add_argument('--news-csv',help='Optional saved News2Market article corpus to join to SEC document dataset')
    secp.add_argument('--dictionary',type=Path,default=LM_PATH)
    secp.add_argument('--no-tfidf',action='store_true')
    secp.add_argument('--output-root',type=Path,default=None)
    m=sub.add_parser('measure',help='Re-score existing locally collected article CSV(s); no network requests')
    m.add_argument('--ticker',required=True,choices=['NVDA','AAPL','GOOGL'])
    m.add_argument('--input-csv',action='append',required=True,help='CSV with title,text,published_date,article_id,source,url')
    m.add_argument('--dictionary',type=Path,default=LM_PATH)
    m.add_argument('--no-tfidf',action='store_true');m.add_argument('--output-root',type=Path,default=None)
    b=sub.add_parser('benchmark',help='Chronological sentiment classification evaluation; independent human labels required')
    b.add_argument('--ticker',required=True,choices=['NVDA','AAPL','GOOGL'])
    b.add_argument('--corpus-csv',required=True)
    b.add_argument('--labels-csv',required=True)
    b.add_argument('--dictionary',type=Path,default=LM_PATH)
    b.add_argument('--output-root',type=Path,default=None)
    joint=sub.add_parser('market',help='Align quality-screened SEC/news LM features with QQQ-relative returns (descriptive only)')
    joint.add_argument('--ticker',required=True,choices=['NVDA','AAPL','GOOGL'])
    joint.add_argument('--features-csv',required=True,type=Path,help='research_features.csv from a previous combined SEC/news measurement run')
    joint.add_argument('--min-directional-hits',type=int,default=3,
        help='Unvalidated diagnostic: below this many LM polarity hits, do not assign textual tone')
    joint.add_argument('--output-root',type=Path,default=None)
    args=p.parse_args(argv)
    try:
        folder,audit={'sec':command_sec,'measure':command_measure,'benchmark':command_benchmark,
                      'market':command_market}[args.action](args)
    except (ValueError,FileNotFoundError,EvaluationNotSupported,sec.SecAccessError) as e:
        p.exit(2,f'Research command stopped: {e}\nCheck Results/<TICKER>/Research for a failure audit; no synthetic findings are generated.\n')
    print(json.dumps({'run_folder':str(folder),'status':audit['status'],
                      'filings':audit.get('disclosures_selected'),
                      'feature_records':(audit.get('outputs',{}).get('output_records')
                          or audit.get('research_scores',{}).get('output_records')),
                      'aligned_events':audit.get('aligned_events')},indent=2))
    return audit

if __name__=='__main__':main()
