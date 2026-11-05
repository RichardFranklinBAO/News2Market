"""News2Market v2.2.8: reproducible, zero-paid-API external news research run.

1) Discover external news automatically using script 15 (or reuse an existing run).
2) Validate full publisher text and create a standalone article dataset in THAT run.
3) Score full text with the official Loughran-McDonald dictionary, and cleaned text.
4) Optionally ask local Ollama for explicitly unverified LLM labels.
5) Write an audit manifest. Never alters Results/<TICKER>/LATEST.txt,
   original 30-article runs, or financial return analysis.

Inside your News2Market directory:
  python Scripts/16_auto_news_research.py --ticker NVDA --existing-run 20261105T151223977161Z
  python Scripts/16_auto_news_research.py --ticker NVDA --query NVIDIA --days 30 --max-external 5
  python Scripts/16_auto_news_research.py --ticker NVDA --query NVIDIA --days 30 --max-external 5 --local-llm --llm-model qwen2.5:1.5b
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'Scripts'
INPUTS = ROOT / 'Inputs'
RESULTS = ROOT / 'Results'
ART_FIELDS = ['article_id','company','source','source_type','title','url','published_date',
              'published_time_quality','text','text_chars','retrieved_utc','synthetic',
              'extraction_strategy','extraction_paragraphs']


def rows_csv(path):
    with path.open('r', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def save_csv(path, rows, fieldnames):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fieldnames,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def invoke(script, env, extra=None, fail_ok=False):
    cmd=[sys.executable, str(SCRIPTS / script)] + (extra or [])
    print('[News2Market] $ ' + ' '.join(cmd),flush=True)
    p=subprocess.run(cmd,cwd=ROOT,env=env,check=False)
    if p.returncode and not fail_ok:
        raise RuntimeError(f'{script} exited with status {p.returncode}')
    return p.returncode


def locate_run(ticker, run_id):
    base=(RESULTS / ticker / 'ExternalAuto').resolve()
    if not re.fullmatch(r'\d{8}T\d{12}Z',run_id):
        raise ValueError('Expected an ExternalAuto run ID such as 20261105T151223977161Z')
    run=(base / run_id).resolve()
    if run.parent!=base or not run.is_dir():
        raise FileNotFoundError(f'ExternalAuto run missing: {run}')
    return run


def discover_new(args):
    base=RESULTS/args.ticker/'ExternalAuto'
    base.mkdir(parents=True,exist_ok=True)
    before={p.name for p in base.iterdir() if p.is_dir()}
    cmd=[sys.executable,str(SCRIPTS/'15_auto_external_news.py'),
         '--ticker',args.ticker,'--query',args.query,'--days',str(args.days),
         '--max-external',str(args.max_external)]
    if args.use_env_proxy:
        cmd.append('--use-env-proxy')
    print('[News2Market] Automatic RSS discovery starting; no manually seeded URLs.',flush=True)
    subprocess.run(cmd,cwd=ROOT,check=True)
    after=[p for p in base.iterdir() if p.is_dir() and p.name not in before]
    new=[p for p in after if (p/'15_external_summary.json').exists()]
    if len(new)!=1:
        raise RuntimeError('Cannot safely identify the newly created ExternalAuto run; no old run will be substituted')
    return new[0]


def select_articles(raw, summary, ticker):
    window=summary.get('date_window',[])
    eligible=[]; excluded=[]; seen_urls=set(); seen_ids=set()
    for row in raw:
        reasons=[]
        aid=str(row.get('article_id','')).strip()
        url=str(row.get('url','')).strip()
        text=str(row.get('text','')).strip()
        date=str(row.get('published_date','')).strip()
        try:
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.hostname:
                reasons.append('not_https_publisher_url')
        except ValueError:
            reasons.append('invalid_url')
        if str(row.get('company','')).upper()!=ticker:
            reasons.append('ticker_mismatch')
        if str(row.get('source_type',''))!='third_party_rss_auto_discovered_unverified':
            reasons.append('source_type_not_expected')
        if str(row.get('synthetic','')).strip().lower() in ('true','1','yes'):
            reasons.append('synthetic_article_not_accepted')
        if len(text)<350:
            reasons.append('body_shorter_than_350_chars')
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',date):
            reasons.append('invalid_date')
        if len(window)==2 and not(window[0]<=date<=window[1]):
            reasons.append('outside_discovery_window')
        if str(row.get('published_time_quality','')).startswith('DATE_MISMATCH'):
            reasons.append('date_mismatch_manual_review')
        if aid in seen_ids or url.rstrip('/') in seen_urls:
            reasons.append('duplicate_article')
        if not aid:
            reasons.append('missing_id')
        if reasons:
            excluded.append({'article_id':aid,'title':row.get('title',''),'reasons':';'.join(reasons)})
        else:
            seen_urls.add(url.rstrip('/'));seen_ids.add(aid)
            eligible.append({k:row.get(k,'') for k in ART_FIELDS})
    return eligible,excluded


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ticker',default='NVDA')
    parser.add_argument('--query',default='NVIDIA')
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--max-external',type=int,default=5)
    parser.add_argument('--existing-run',default='',help='Existing run ID (no network); useful for analyzing your first two discovered articles')
    parser.add_argument('--local-llm',action='store_true',help='Optional: local Ollama only, unvalidated experimental labels')
    parser.add_argument('--llm-model',default='qwen2.5:1.5b')
    parser.add_argument('--llm-max-chars',type=int,default=1000)
    parser.add_argument('--use-env-proxy',action='store_true')
    args=parser.parse_args()
    args.ticker=args.ticker.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,11}',args.ticker):parser.error('Invalid ticker')
    if not 1<=args.days<=90:parser.error('days must be in 1..90')
    if not 1<=args.max_external<=20:parser.error('max-external must be in 1..20')
    if ':cloud' in args.llm_model.casefold():parser.error('Paid cloud model prohibited')
    if not 200<=args.llm_max_chars<=2200:parser.error('llm-max-chars must be 200..2200')
    expected=INPUTS/'Loughran-McDonald_MasterDictionary_1993-2025.csv'
    if not expected.exists():
        parser.error('Install official LM dictionary in Inputs/ first; no synthetic lexicon substitute')
    if not (SCRIPTS/'15_auto_external_news.py').exists() and not args.existing_run:
        parser.error('Install Scripts/15_auto_external_news.py from v2.2.7 first')
    run=locate_run(args.ticker,args.existing_run) if args.existing_run else discover_new(args)
    summary_path=run/'15_external_summary.json'
    articles_path=run/'15_external_articles.csv'
    if not summary_path.exists() or not articles_path.exists():
        raise FileNotFoundError('Missing auto-news run summary/articles; refusing to infer input or use another run')
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    if summary.get('ticker')!=args.ticker:
        raise RuntimeError('Auto news ticker does not match requested ticker')
    raw=rows_csv(articles_path)
    verified,excluded=select_articles(raw,summary,args.ticker)
    save_csv(run/'04_articles.csv',verified,ART_FIELDS)
    save_csv(run/'16_external_exclusions.csv',excluded,['article_id','title','reasons'])
    context={
        'ticker':args.ticker,'mode':'live','source':'external_rss_auto',
        'start_date':summary['date_window'][0],'end_date':summary['date_window'][1],
        'external_run':run.name,'research_only':True,
        'external_articles_have_only_DATE_level_publication_time':True,
        'no_market_return_join_or_price_regression':True,
    }
    save_json(run/'context.json',context)
    audit={
        'version':'News2Market_v2.2.8_external_research',
        'external_run':str(run),'sources':summary.get('working_feeds'),
        'unique_relevant_links':summary.get('unique_relevant_links'),
        'retrieved_full_texts':len(raw),'eligible_full_texts':len(verified),
        'excluded_count':len(excluded),'excluded':excluded,
        'lm_status':'not_run','ollama_status':'not_requested',
        'never_modifies_latest_txt':True,'never_merges_into_historical_return_regression':True,
        'publication_time_warning':'Page and feed dates lack verified intraday availability; no causal/event-study inference or same-day return merge.',
        'llm_warning':'Structured labels are not independently human-validated and may be systematically misclassified; invalid scores must remain missing.',
    }
    audit_path=run/'16_research_audit.json'
    if not verified:
        audit['lm_status']='no_full_text_available'
        save_json(audit_path,audit)
        print('[News2Market] No qualified full texts: saved audit, no artificial LM measurements.',flush=True)
        return
    env={**os.environ,'N2M_RESULTS_DIR':str(run),'N2M_CONTEXT':str(run/'context.json')}
    try:
        invoke('05_lm_sentiment.py',env)
        invoke('11_prepare_text.py',env)
        invoke('11b_lm_cleaned.py',env)
        audit['lm_status']='completed'
        lm=rows_csv(run/'05_lm_labels.csv')
        cleaned=rows_csv(run/'11b_lm_original_vs_cleaned.csv')
        by_id={r['article_id']:r for r in cleaned}
        output=[]
        for r in lm:
            c=by_id.get(r['article_id'],{})
            output.append({
                'article_id':r['article_id'],'title':r['title'],'url':r['url'],
                'source':r['source'],'published_date':r['published_date'],
                'published_time_quality': next((a['published_time_quality'] for a in verified if a['article_id']==r['article_id']),'unknown'),
                'lm_raw_score':r.get('score',''),
                'lm_raw_sentiment':r.get('sentiment',''),
                'lm_raw_polarity_hits':r.get('lm_polarity_hits',''),
                'lm_clean_score':c.get('lm_clean_score',''),
                'lm_clean_unscorable':c.get('lm_clean_unscorable',''),
                'lm_cleaning_rule':c.get('cleaning_rule',''),
                'economic_measurement_status':'LM exploratory measurement only; not human-validated',
            })
        save_csv(run/'16_external_lm_summary.csv',output,
            ['article_id','title','url','source','published_date','published_time_quality',
             'lm_raw_score','lm_raw_sentiment','lm_raw_polarity_hits','lm_clean_score',
             'lm_clean_unscorable','lm_cleaning_rule','economic_measurement_status'])
        audit['lm_articles']=len(output)
        audit['lm_polarity_hit_articles']=sum(str(r.get('lm_raw_polarity_hits','0')).isdigit() and int(r['lm_raw_polarity_hits'])>0 for r in output)
        if args.local_llm:
            env['N2M_LLM_MODEL']=args.llm_model
            env['N2M_LLM_CONTEXT']='2048'
            env['N2M_LLM_MAX_CHARS']=str(args.llm_max_chars)
            env['N2M_LLM_MAX_ARTICLES']=str(min(len(verified),30))
            code=invoke('12_local_llm_labels.py',env,fail_ok=True)
            audit['ollama_status']='completed_with_structural_flags_not_human_validated' if code==0 else 'failed_or_no_valid_labels_outputs_may_be_preserved'
            audit['ollama_model']=args.llm_model
            audit['ollama_exit_code']=code
    finally:
        save_json(audit_path,audit)
    print('\n[News2Market] AUTO EXTERNAL RESEARCH COMPLETE',flush=True)
    print('[News2Market] Folder: '+str(run),flush=True)
    print('[News2Market] LM summary: '+str(run/'16_external_lm_summary.csv'),flush=True)
    print('[News2Market] Audit: '+str(audit_path),flush=True)
    print('[News2Market] Prior 30-article research and LATEST.txt unchanged. No returns estimated.',flush=True)

if __name__=='__main__':
    main()
