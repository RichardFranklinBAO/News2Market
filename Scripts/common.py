"""Shared, audited paths and limited-network utilities."""
from __future__ import annotations
import csv, json, os, re, time
from pathlib import Path
from urllib.parse import urlparse
import yaml
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT/'Inputs'
RESULTS = Path(os.environ.get('N2M_RESULTS_DIR',str(ROOT/'Results')))
RESULTS.mkdir(parents=True,exist_ok=True)

def config():
    cfg=yaml.safe_load((INPUTS/'config.yaml').read_text(encoding='utf-8'))
    context=os.environ.get('N2M_CONTEXT')
    if context:
        ctx=json.loads(Path(context).read_text(encoding='utf-8'))
        cfg['project'].update({key:ctx[key] for key in ('ticker','benchmark','start_date','end_date') if key in ctx})
        cfg['_context']=ctx
    else:
        cfg['_context']={}
    return cfg

def write_csv(path, rows, fields=None):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or (list(rows[0]) if rows else None)
    if not fields: raise ValueError(f'CSV columns unknown for {path}')
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def read_csv(path):
    path=Path(path)
    if not path.exists(): raise FileNotFoundError(f'File not found: {path}')
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))

def json_dump(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def clean_text(s): return re.sub(r'\s+',' ',s or '').strip()

def message(s): print('[News2Market] '+str(s),flush=True)

def sec_ua():
    ua=os.getenv('N2M_SEC_USER_AGENT','').strip()
    if not ua or '@' not in ua:
        raise RuntimeError('SEC access requires a truthful User-Agent with your email. Set N2M_SEC_USER_AGENT="Your Name your_email@example.com" before using --source sec/auto for non-NVDA.')
    return ua

def fetch_json(url, user_agent, timeout=20, retries=1):
    last=None
    for attempt in range(retries+1):
        try:
            r=requests.get(url,headers={'User-Agent':user_agent,'Accept':'application/json'},timeout=timeout)
            if r.status_code in (403,429): raise RuntimeError(f'HTTP {r.status_code} at {url}; respect provider restrictions')
            r.raise_for_status()
            return r.json()
        except (requests.RequestException,ValueError,RuntimeError) as e:
            last=e
            if attempt<retries: time.sleep(3)
    raise RuntimeError(f'JSON request failed: {last}') from last
