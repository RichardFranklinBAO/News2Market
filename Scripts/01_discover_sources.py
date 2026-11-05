"""Free SEC recent submissions metadata; optional GDELT news discovery only (NO article bodies)."""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta,date
import requests
from urllib.parse import quote
from common import RESULTS, config, sec_ua, fetch_json, write_csv, json_dump, message

FIELDS=['source_type','source','title','url','published_date','published_time_quality','form','accession','primary_document']

def make_sec_candidates(submissions,start,end,cik,max_records=50):
    recent=submissions.get('filings',{}).get('recent',{})
    arr=[]
    for i,form in enumerate(recent.get('form',[])):
        date=(recent.get('filingDate') or [])[i] if i < len(recent.get('filingDate') or []) else ''
        if form not in ('8-K','10-Q','10-K','8-K/A','10-Q/A','10-K/A') or not (start<=date<=end): continue
        primary=(recent.get('primaryDocument') or [])[i] if i < len(recent.get('primaryDocument') or []) else ''
        acc=(recent.get('accessionNumber') or [])[i] if i < len(recent.get('accessionNumber') or []) else ''
        if not primary or not acc: continue
        accession=acc.replace('-','')
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary}'
        arr.append({'source_type':'first_party_filing','source':'SEC EDGAR','title':f'{form} filed {date}',
          'url':url,'published_date':date,'published_time_quality':'filing_date_only',
          'form':form,'accession':acc,'primary_document':primary})
        if len(arr)>=max_records: break
    return arr

def gdelt_discover(company, ticker, start, end, count):
    # Metadata only, not a license to download arbitrary publishers' article text.
    name=company.replace('CORPORATION','').replace('INC.','').strip()
    query='"'+name.replace('"','')+'"'
    # GDELT DOC 2.0 exposes a limited recent window (not multi-year history).
    recent_floor=(datetime.now(timezone.utc).date()-timedelta(days=85)).isoformat()
    effective_start=max(start,recent_floor)
    if effective_start>end:
        message('GDELT has no supported recent dates in requested range; returning zero discovery links.')
        return []
    if effective_start>start:
        message(f'GDELT recent-window bound: requested {start} but using {effective_start} onward.')
    params={'query':query,'mode':'artlist','format':'json','maxrecords':min(count,50),
           'startdatetime':effective_start.replace('-','')+'000000',
           'enddatetime':end.replace('-','')+'235959','sort':'datedesc'}
    r=requests.get('https://api.gdeltproject.org/api/v2/doc/doc',params=params,
        headers={'User-Agent':'News2Market academic research (news discovery only)'},timeout=30)
    r.raise_for_status(); data=r.json()
    return [{'title':a.get('title',''),'url':a.get('url',''),
             'seen_date':a.get('seendate',''),'domain':a.get('domain',''),
             'source_type':'external_news_metadata_unverified','ticker':ticker}
             for a in data.get('articles',[]) if a.get('url')]

def main():
    cfg=config(); ctx=cfg['_context']; source=ctx['source']; ticker=cfg['project']['ticker']
    info=json.loads((RESULTS/'00_company.json').read_text(encoding='utf-8'))
    rows=[]; gdelt=[]; sec_url=None
    if ctx['mode']=='live' and source=='sec':
        sec_url=f"https://data.sec.gov/submissions/CIK{info['cik']}.json"
        submissions=fetch_json(sec_url,sec_ua())
        rows=make_sec_candidates(submissions,cfg['project']['start_date'],cfg['project']['end_date'],info['cik'],ctx['max_articles'])
    if ctx['mode']=='live' and ctx.get('gdelt',False):
        try:
            gdelt=gdelt_discover(info['name'],ticker,cfg['project']['start_date'],cfg['project']['end_date'],ctx['max_articles'])
        except Exception as e:
            message(f'GDELT discovery unavailable: {e}; optional metadata discovery skipped, no fake articles inserted.')
    write_csv(RESULTS/'01_discovered_filings.csv',rows,FIELDS)
    write_csv(RESULTS/'01_gdelt_metadata_only.csv',gdelt,['title','url','seen_date','domain','source_type','ticker'])
    json_dump(RESULTS/'01_discovery_audit.json',{'source':source,'sec_submissions_url':sec_url,
       'filings_discovered':len(rows),'gdelt_link_metadata':len(gdelt),
       'warning':'GDELT URL metadata only; actual full text included in LM only if separately fetched and verified. GDELT has recent-history coverage limits; external URLs may contain syndicated PR.'})
    message(f'Discovery: {len(rows)} SEC filings; {len(gdelt)} external news links (metadata only).')

if __name__=='__main__': main()
