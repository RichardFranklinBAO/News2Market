"""Free one-command News2Market runner. Live mode never falls back to synthetic data."""
from __future__ import annotations
import argparse, os, re, subprocess,sys,json
from datetime import datetime,timezone,date
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SCRIPTS=ROOT/'Scripts'
INPUTS=ROOT/'Inputs'
RESULTS=ROOT/'Results'
DATA_STAGES=['00_resolve_company.py','01_discover_sources.py','02_scrape_articles.py',
             '03_collect_filings.py','03b_scrape_external.py','04_clean_deduplicate.py','05_lm_sentiment.py','06_event_tags.py']
ANALYSIS_STAGES=['07_get_prices.py','08_build_signals.py','09_validate.py']

def run(script,env):
    command=[sys.executable,str(SCRIPTS/script)]
    print('\n$ '+' '.join(command),flush=True)
    subprocess.run(command,cwd=ROOT,env=env,check=True)

def parse():
    p=argparse.ArgumentParser(description='News2Market v2.2: free research text pipeline + optional local LLM')
    p.add_argument('--ticker',default='NVDA',help='US stock ticker; demo supports only NVDA')
    p.add_argument('--benchmark',default='QQQ')
    p.add_argument('--mode',choices=['demo','live'],default='demo')
    p.add_argument('--source',choices=['auto','nvidia','sec'],default='auto',
                   help='auto: nvidia for NVDA, otherwise SEC filings')
    p.add_argument('--max-articles',type=int,default=24)
    p.add_argument('--start',default=None,help='YYYY-MM-DD; article inclusive start')
    p.add_argument('--end',default=None,help='YYYY-MM-DD; article inclusive end')
    p.add_argument('--gdelt',action='store_true',help='Optional news link discovery only; does not scrape publisher text')
    p.add_argument('--web-news',action='store_true',help='Experimental: discover via GDELT and scrape permitted external web articles; not whole Internet')
    p.add_argument('--max-external',type=int,default=10,help='Maximum verified external full texts (1-20)')
    p.add_argument('--local-llm',action='store_true',help='After collection, label with a LOCAL Ollama model; no paid API')
    p.add_argument('--clean-only',action='store_true',help='Clean known boilerplates and compare raw vs cleaned LM on latest collection; no Ollama required')
    p.add_argument('--llm-only',action='store_true',help='Only prepare/label already collected texts in latest result folder; no prices or network scraping')
    p.add_argument('--llm-model',default='qwen2.5:3b',help='Local Ollama model name, never :cloud')
    p.add_argument('--llm-max-articles',type=int,default=5,help='Limit local model calls to 1-30 articles')
    p.add_argument('--collect-only',action='store_true',help='Collect+LM first; no price CSV needed')
    p.add_argument('--resume',action='store_true',help='Reuse latest collection for this ticker and run market analysis only')
    p.add_argument('--company-name',default=None,help='Optional user-confirmed company name (requires --cik)')
    p.add_argument('--cik',default=None,help='Optional user-confirmed SEC CIK (requires --company-name)')
    args=p.parse_args()
    args.ticker=args.ticker.strip().upper(); args.benchmark=args.benchmark.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,11}',args.ticker): p.error('Invalid ticker format')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,11}',args.benchmark): p.error('Invalid benchmark format')
    if args.ticker==args.benchmark: p.error('Ticker and benchmark must differ')
    if not 1<=args.max_articles<=50: p.error('Safety: 1 <= --max-articles <= 50')
    if args.mode=='demo' and (args.ticker!='NVDA' or args.benchmark!='QQQ'):
        p.error('Synthetic demo fixtures are for NVDA and QQQ only')
    if not 1<=args.max_external<=20: p.error('1 <= --max-external <= 20')
    if not 1<=args.llm_max_articles<=30: p.error('1 <= --llm-max-articles <= 30')
    if ':cloud' in args.llm_model.lower(): p.error('Cloud models are not allowed in free-only mode')
    if args.clean_only and (args.llm_only or args.collect_only or args.resume): p.error('--clean-only is a standalone mode')
    if args.llm_only and (args.collect_only or args.resume): p.error('--llm-only cannot be combined with --resume or --collect-only')
    if args.collect_only and args.resume: p.error('--collect-only and --resume cannot be combined')
    if bool(args.company_name)!=bool(args.cik): p.error('--company-name and --cik must be provided together')
    if args.source=='nvidia' and args.ticker!='NVDA': p.error('NVIDIA scraper cannot run for other tickers')
    return args

def main():
    args=parse()
    import yaml
    cfg=yaml.safe_load((INPUTS/'config.yaml').read_text(encoding='utf-8'))
    start=args.start or cfg['project']['start_date']
    end=args.end or cfg['project']['end_date']
    if date.fromisoformat(start)>date.fromisoformat(end): raise ValueError('start must be <= end')
    source=('nvidia' if args.ticker=='NVDA' else 'sec') if args.source=='auto' else args.source
    if args.mode=='demo': source='nvidia'
    parent=RESULTS/args.ticker
    parent.mkdir(parents=True,exist_ok=True)
    latest=parent/'LATEST.txt'
    if args.resume or args.llm_only or args.clean_only:
        if not latest.exists(): raise RuntimeError(f'No previous collection for {args.ticker}; run --collect-only first')
        run_name=latest.read_text(encoding='utf-8').strip()
        work=parent/Path(run_name).name
        if not work.is_dir(): raise RuntimeError('LATEST folder missing')
        ctx=json.loads((work/'context.json').read_text(encoding='utf-8'))
        if ctx['mode']!=args.mode: raise RuntimeError(f'Resume mode must match original collection mode: {ctx["mode"]}')
        if ctx['ticker']!=args.ticker or ctx['benchmark']!=args.benchmark:
            raise RuntimeError('Cannot resume a different ticker/benchmark')
        if not (work/'06_labels_with_events.csv').exists():
            raise RuntimeError('No finished collection/labels in latest run; collect first')
    else:
        timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        work=parent/timestamp
        work.mkdir(parents=True,exist_ok=False)
        ctx={'ticker':args.ticker,'benchmark':args.benchmark,'mode':args.mode,
             'source':source,'start_date':start,'end_date':end,
             'max_articles':args.max_articles,'gdelt':args.gdelt or args.web_news,
             'web_news':args.web_news,'max_external':args.max_external,
             'company_name':args.company_name,'cik':args.cik,
             'demo_articles_path':str(INPUTS/'demo_articles.csv'),
             'free_only':True,'uses_paid_apis':False}
        (work/'context.json').write_text(json.dumps(ctx,indent=2),encoding='utf-8')
        latest.write_text(work.name,encoding='utf-8')
    env={**os.environ,'N2M_RESULTS_DIR':str(work),'N2M_CONTEXT':str(work/'context.json')}
    manifest=work/'00_run_manifest.json'
    def status(value,success,extra=None):
        manifest.write_text(json.dumps({'status':value,'success':success,'ticker':ctx['ticker'],
          'mode':ctx['mode'],'source':ctx['source'],'run_folder':str(work),
          'updated_utc':datetime.now(timezone.utc).isoformat(),
          'free_only':True,'paid_api_calls':0,**(extra or {})},indent=2),encoding='utf-8')
    status('RUNNING',False)
    try:
        if not (args.resume or args.llm_only or args.clean_only):
            if args.mode=='demo':run('create_demo_inputs.py',env)
            # Official LM file remains a local research input, not a mock substitute.
            expected=INPUTS/'Loughran-McDonald_MasterDictionary_1993-2025.csv'
            if not expected.exists(): raise FileNotFoundError(
              f'Official LM CSV missing at {expected}. Copy the official 1993-2025 CSV into Inputs/; see Python.md.')
            for stage in DATA_STAGES:run(stage,env)
        if args.local_llm or args.llm_only or args.clean_only:
            env['N2M_LLM_MODEL']=args.llm_model
            env['N2M_LLM_MAX_ARTICLES']=str(args.llm_max_articles)
            run('11_prepare_text.py',env)
            run('11b_lm_cleaned.py',env)
            if not args.clean_only: run('12_local_llm_labels.py',env)
        if args.clean_only:
            status('CLEAN_LM_COMPARISON_COMPLETE',True)
            print(f'CLEAN LM COMPARISON COMPLETE: {work}/11b_lm_original_vs_cleaned.csv')
            return
        if args.llm_only:
            status('LOCAL_LLM_COMPLETE',True,{'model':args.llm_model,'max_articles':args.llm_max_articles})
            print(f'LOCAL LLM COMPLETE: {work}/12_local_llm_labels.csv')
            return
        if args.collect_only:
            status('COLLECTION_COMPLETE; PRICES_NOT_RUN',True,{'stages':DATA_STAGES})
            print(f'\nCOLLECTION SUCCESS: {work}\nWhen you have Inputs/prices/{args.ticker}.csv and Inputs/prices/{args.benchmark}.csv, run:',flush=True)
            print(f'python run_all.py --mode {args.mode} --ticker {args.ticker} --benchmark {args.benchmark} --resume')
            return
        for stage in ANALYSIS_STAGES:run(stage,env)
        status('FULL_PIPELINE_COMPLETE',True,{'stages':DATA_STAGES+ANALYSIS_STAGES})
        print(f'\nSUCCESS: {work}/09_analysis_summary.json')
    except (subprocess.CalledProcessError,FileNotFoundError,RuntimeError) as e:
        status('FAILED',False,{'error':str(e),'can_resume_after_csv':(work/'06_labels_with_events.csv').exists()})
        print(f'\nFAILED: {e}\nExisting partial files are preserved in {work}. No synthetic substitution.',file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__':main()
