"""100% FREE: ingest user-supplied Nasdaq historical CSV without paid APIs.

Supported formats:
- Nasdaq exported: Date,Close/Last,Volume,Open,High,Low, dates MM/DD/YYYY,
  dollar symbols in prices, descending chronology.
- Normalized: Date,Close or Date,Adj Close, dates YYYY-MM-DD.

Raw `Close/Last` is NOT a dividend-adjusted total-return price. Preserve this
important distinction in the price audit. Never claim dividend adjustment.
"""
from __future__ import annotations
from pathlib import Path
import csv, math, hashlib
from datetime import datetime, date
from common import INPUTS,RESULTS,config,read_csv,write_csv,json_dump,message

PREFERRED=['adjclose','adjustedclose','adjustedclosingprice']
RAW=['close','closingprice','closelast','last']

def key(x):
    return ''.join(c for c in str(x).lower() if c.isalnum())

def parse_date(text):
    text=str(text).strip()
    # Explicitly disambiguate US Nasdaq date MM/DD/YYYY from ISO dates.
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%m/%d/%y'):
        try: return datetime.strptime(text,fmt).date().isoformat()
        except ValueError: pass
    raise ValueError(f'Unrecognized date {text!r}; expected YYYY-MM-DD or MM/DD/YYYY')

def parse_price_csv(path):
    path=Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'Missing REAL market CSV: {path}. Download legitimate historical data and put them at Inputs/prices/<TICKER>.csv; do not use demo prices.')
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames: raise ValueError(f'Empty CSV: {path}')
        normalized={key(s):s for s in reader.fieldnames}
        d=normalized.get('date')
        p=next((normalized[k] for k in PREFERRED if k in normalized),None)
        kind='adjusted_close_provider_label'
        if p is None:
            p=next((normalized[k] for k in RAW if k in normalized),None)
            kind='raw_close_unadjusted'
        if d is None or p is None:
            raise ValueError(f'{path.name}: need Date and Adj Close / Close / Close/Last; found {reader.fieldnames}')
        seen=set();rows=[];raw_count=0
        for line_number,line in enumerate(reader,start=2):
            if not any(str(v or '').strip() for v in line.values()):continue
            raw_count+=1
            try:
                day=parse_date(line[d])
                numeric=str(line[p]).strip().replace(',','').replace('$','')
                value=float(numeric)
                if not math.isfinite(value) or value<=0:
                    raise ValueError(f'Nonpositive/nonfinite close {numeric!r}')
            except (TypeError,ValueError) as e:
                raise ValueError(f'{path.name} line {line_number}: {e}') from e
            if day in seen: raise ValueError(f'Duplicate price date {day} in {path}')
            seen.add(day)
            rows.append({'date':day,'close':value})
    rows.sort(key=lambda x:x['date'])
    if not rows: raise ValueError(f'No valid closes in {path}')
    return rows,kind

def combine_prices(asset,bench,ticker,benchmark):
    a={x['date']:x['close'] for x in asset}
    b={x['date']:x['close'] for x in bench}
    common=sorted(a.keys() & b.keys())
    if len(common)<3: raise RuntimeError('Fewer than 3 matching sessions in asset and benchmark CSVs')
    return [{'date':d,f'{ticker}_close':a[d],f'{benchmark}_close':b[d],
             'source':'local_user_supplied_real_csv'} for d in common]

def file_audit(path,rows,kind):
    path=Path(path)
    return {'file':str(path.relative_to(INPUTS.parent)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'first_date':rows[0]['date'],'last_date':rows[-1]['date'],
            'row_count':len(rows),'price_kind':kind,
            'cash_dividends_adjusted':kind=='adjusted_close_provider_label',
            'price_basis_note':('Labelled Adj Close by source; verify provider methodology.' if kind!='raw_close_unadjusted'
                else 'Raw Close/Last / Close price: NOT dividend adjusted; potentially split adjusted by provider; not total-return data.')}

def main():
    cfg=config();ctx=cfg['_context'];ticker=cfg['project']['ticker'];benchmark=cfg['project']['benchmark']
    if ctx['mode']=='demo':
        rows=read_csv(INPUTS/'demo_prices.csv')
        kinds={'asset':'synthetic','benchmark':'synthetic'}
        files={'asset':None,'benchmark':None}
        coverage={'paired_start':rows[0]['date'],'paired_end':rows[-1]['date'],'paired_count':len(rows)}
    else:
        pa=INPUTS/'prices'/f'{ticker}.csv';pb=INPUTS/'prices'/f'{benchmark}.csv'
        a,ka=parse_price_csv(pa);b,kb=parse_price_csv(pb)
        rows=combine_prices(a,b,ticker,benchmark)
        kinds={'asset':ka,'benchmark':kb}
        files={'asset':file_audit(pa,a,ka),'benchmark':file_audit(pb,b,kb)}
        coverage={'paired_start':rows[0]['date'],'paired_end':rows[-1]['date'],
                  'paired_count':len(rows),'unmatched_asset_dates':len(a)-len(rows),
                  'unmatched_benchmark_dates':len(b)-len(rows)}
        message(f'Parsed REAL historical CSV: {ticker} ({len(a)} days), {benchmark} ({len(b)} days), {len(rows)} matching days; 0 market API requests.')
        if ka=='raw_close_unadjusted' or kb=='raw_close_unadjusted':
            message('CAUTION: Nasdaq Close/Last is NOT adjusted for cash dividends; this is PRICE RETURN, not TOTAL RETURN. See 07_price_audit.json.')
    write_csv(RESULTS/'07_prices.csv',rows,['date',f'{ticker}_close',f'{benchmark}_close','source'])
    json_dump(RESULTS/'07_price_audit.json',{'mode':ctx['mode'],'ticker':ticker,'benchmark':benchmark,
       'observations':len(rows),'price_kind':kinds,'input_files':files,'coverage':coverage,
       'return_definition':'close-to-close price returns; asset-minus-benchmark difference, NOT dividend total return if Close/Last inputs are used',
       'warning':'Confirm source/ticker, splits and dividends; Nasdaq close/last does not establish dividend-adjusted total return.'})
    message(f'Paired sessions: {len(rows)} ({ticker} vs {benchmark}); 0 price API requests.')

if __name__=='__main__':main()
