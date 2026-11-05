"""Collect actual SEC HTML filing bodies using polite robots-aware fetcher."""
from __future__ import annotations
import hashlib
from datetime import datetime,timezone
from common import RESULTS, config, read_csv, write_csv, message, json_dump, clean_text, sec_ua
from nvidia_scraper import PoliteFetcher, extract_article_text_with_audit, extraction_diagnostics, FIELDS
from bs4 import BeautifulSoup

def extract_sec_filing_body(html):
    """SEC documents often use tables and inline font tags instead of p tags."""
    txt,audit=extract_article_text_with_audit(html)
    if len(txt)>=80: return txt,audit
    soup=BeautifulSoup(html,"html.parser")
    for node in soup.select("script,style,nav,form,footer,noscript"):
        node.decompose()
    body=soup.body or soup
    fallback=clean_text(body.get_text(" ",strip=True))[:30000]
    return fallback,{"strategy":"SEC_plain_visible_text_fallback_NEEDS_MANUAL_AUDIT","paragraphs":0}


def main():
    cfg=config();ctx=cfg['_context']; items=read_csv(RESULTS/'01_discovered_filings.csv')
    out=[]; skipped=[]; count=0
    if items:
        webcfg={**cfg['collection'], 'user_agent':sec_ua(),
                'min_seconds_between_requests':max(2.0,cfg['collection']['min_seconds_between_requests'])}
        fetcher=PoliteFetcher(webcfg)
        for item in items[:ctx['max_articles']]:
            try:
                html=fetcher.get(item['url'])
                text,audit=extract_sec_filing_body(html)
                if len(text)<cfg['collection']['min_article_chars']:
                    skipped.append({'url':item['url'],'reason':'short_body','diagnostics':extraction_diagnostics(html)})
                    continue
                out.append({'article_id':hashlib.sha256(item['url'].encode()).hexdigest()[:16],
                    'company':cfg['project']['ticker'],'source':'SEC EDGAR',
                    'source_type':'first_party_filing','title':item['title'], 'url':item['url'],
                    'published_date':item['published_date'],
                    'published_time_quality':'filing_date_only_no_acceptance_time',
                    'text':text,'text_chars':len(text),
                    'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                    'synthetic':False,'extraction_strategy':audit['strategy'],
                    'extraction_paragraphs':audit['paragraphs']})
            except Exception as e:
                skipped.append({'url':item['url'],'reason':str(e)[:250]})
        count=fetcher.count
    write_csv(RESULTS/'03_filings.csv',out,FIELDS)
    json_dump(RESULTS/'03_filings_audit.json',{'filings_collected':len(out),
       'http_requests':count,'skipped':skipped,
       'warning':'Regulatory filing dates are date-only here; section content may include exhibits and legal boilerplate. Manual audit required.'})
    message(f'SEC full-text filings: {len(out)}, HTTP requests={count}, skipped={len(skipped)}.')

if __name__=='__main__': main()
