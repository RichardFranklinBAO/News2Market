"""Merge auditable article bodies; never treat discovery-only links as text."""
from __future__ import annotations
import hashlib
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from common import RESULTS, config, read_csv,write_csv,json_dump,message,clean_text
from nvidia_scraper import FIELDS

def canonical_url(url):
    parts=urlsplit(url)
    params=[(k,v) for k,v in parse_qsl(parts.query) if not (k.startswith('utm_') or k in ('fbclid','gclid'))]
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path.rstrip('/'),urlencode(sorted(params)),''))

def dedupe(rows):
    out=[];seen_urls=set();seen_text=set();excluded=[]
    for row in rows:
        url=canonical_url(row.get('url',''))
        body=clean_text(row.get('text',''))
        digest=hashlib.sha256(body.encode()).hexdigest()
        if not body or len(body)<80:
            excluded.append({'url':url,'reason':'missing_or_short_body'});continue
        if url in seen_urls or digest in seen_text:
            excluded.append({'url':url,'reason':'duplicate_url_or_same_body'});continue
        out.append({**row,'url':url,'text':body,'text_chars':len(body)})
        seen_urls.add(url);seen_text.add(digest)
    return out,excluded

def main():
    rows=read_csv(RESULTS/'02_web_articles.csv')+read_csv(RESULTS/'03_filings.csv')
    external=RESULTS/'03b_external_articles.csv'
    if external.exists(): rows+=read_csv(external)
    cleaned,excluded=dedupe(rows)
    if not cleaned: raise RuntimeError('No full-text articles collected; GDELT links without bodies are deliberately NOT scored. Use NVDA --source nvidia, or verify SEC access and filing dates.')
    write_csv(RESULTS/'04_articles.csv',cleaned,FIELDS)
    json_dump(RESULTS/'04_cleaning_audit.json',{'raw_count':len(rows),'kept':len(cleaned),
        'excluded':excluded,'source_counts':{s:sum(x['source_type']==s for x in cleaned)
                            for s in set(x['source_type'] for x in cleaned)},
        'warning':'Exact normalized text/URL dedup only; syndication paraphrases can remain. Review legal/footer noise.'})
    message(f'Clean full-body records: {len(cleaned)} kept, {len(excluded)} excluded.')

if __name__=='__main__': main()
