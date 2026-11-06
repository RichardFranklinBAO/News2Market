"""Validate issuer identity BEFORE assigning a selected ticker to imported data.

Direct identifiers are stronger than entity mentions; uncertain rows do not enter
company-level analysis. A heuristic name match is disclosed, never called verified.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

ISSUERS = {
    'NVDA': {'cik':'1045810','titles':(r'\bnvidia\b',r'\bnvda\b'), 'host':'nvidianews.nvidia.com'},
    'AAPL': {'cik':'320193','titles':(r'\bapple\b',r'\baapl\b'), 'host':'apple.com'},
    'GOOGL':{'cik':'1652044','titles':(r'\balphabet\b',r'\bgoogle\b',r'\bgoogl\b'), 'host':'blog.google'},
}

def _normalize_cik(value):
    if value is None or str(value).strip()=='':return ''
    s=str(value).strip()
    if not s.isdigit():return '#invalid'
    return str(int(s))

def _url_cik(url):
    try:
        obj=urlparse(str(url or ''))
        if obj.scheme!='https' or (obj.hostname or '').lower() not in ('www.sec.gov','sec.gov','data.sec.gov'):
            return ''
        m=re.search(r'^/Archives/edgar/data/(\d+)/',obj.path,re.I)
        if m:return _normalize_cik(m.group(1))
        m=re.fullmatch(r'/submissions/CIK(\d+)\.json',obj.path,re.I)
        return _normalize_cik(m.group(1)) if m else ''
    except (TypeError,ValueError):return ''

def classify(row,ticker):
    """Return (accepted, evidence, reason); never mutate input data."""
    ticker=ticker.upper()
    profile=ISSUERS[ticker]
    provided=str(row.get('ticker') or row.get('symbol') or '').strip().upper()
    if provided and provided!=ticker:
        return False,'ticker_conflict',f'input ticker {provided} differs from {ticker}'
    cik=_normalize_cik(row.get('cik') or row.get('CIK'))
    url_cik=_url_cik(row.get('url'))
    for kind, candidate in [('cik',cik),('sec_url_cik',url_cik)]:
        if candidate and candidate!=profile['cik']:
            return False,kind+'_conflict',f'{kind} does not match selected company'
    if provided:return True,'ticker_exact',''
    if cik:return True,'cik_exact',''
    if url_cik:return True,'sec_url_cik_exact',''
    title=str(row.get('title') or '')
    for pattern in profile['titles']:
        if re.search(pattern,title,re.I):
            if ticker=='AAPL' and re.search(r'\b(apple orchard|apple cider|apple pie|apple harvest|apple tree|apple fruit)\b',title,re.I) and not re.search(r'\b(iphone|ipad|macbook|aapl|apple inc)\b',title,re.I):
                break
            return True,'title_alias_heuristic','title mention is NOT verified issuer identity'
    try:
        host=(urlparse(str(row.get('url') or '')).hostname or '').lower()
    except ValueError:host=''
    # Only explicitly issuer-owned hosts; never treat search/publisher domains as issuer proof.
    if host==profile['host'] or host.endswith('.'+profile['host']):
        return True,'issuer_host_heuristic','issuer host is not a verified document-level match'
    return False,'unverified','No company ticker, CIK, SEC URL CIK or unambiguous title/issuer-host evidence'

def validate_rows(rows,ticker):
    accepted=[];rejected=[];counts={}
    for row in rows:
        ok,evidence,why=classify(row,ticker)
        counts[evidence]=counts.get(evidence,0)+1
        if ok:
            new=dict(row)
            new['ticker']=ticker
            new['company_identity_evidence']=evidence
            accepted.append(new)
        else:
            rejected.append({'article_id':str(row.get('article_id') or ''),
                             'reason':evidence,'detail':why})
    return accepted,{'input_rows':len(rows),'accepted':len(accepted),'rejected':len(rejected),
                     'evidence_counts':counts,'rejected_rows':rejected[:100],
                     'warning':'Title/issuer-host matches are heuristic; not independently verified entity resolution'}
