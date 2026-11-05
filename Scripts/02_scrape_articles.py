"""Genuine HTML scraping of NVIDIA first-party news; restricted to ticker NVDA."""
from __future__ import annotations
from common import RESULTS, config, write_csv, json_dump, message, read_csv
from nvidia_scraper import collect_live, FIELDS

def main():
    cfg=config(); ctx=cfg['_context']
    if ctx['mode']=='demo':
        rows=read_csv(cfg['_context']['demo_articles_path'])[:ctx['max_articles']]
        count=0
    elif ctx['source']=='nvidia':
        if cfg['project']['ticker']!='NVDA':
            raise RuntimeError('NVIDIA crawler must never run for another ticker')
        rows,count=collect_live(cfg,ctx['max_articles'])
    else:
        rows=[]; count=0
    write_csv(RESULTS/'02_web_articles.csv',rows,FIELDS)
    json_dump(RESULTS/'02_scrape_audit.json',{'source':ctx['source'],
        'articles':len(rows),'http_requests':count,
        'note':'NVIDIA is first-party PR, not independent news. HTML extraction must be manually spot-checked.'})
    message(f'Web HTML scraping: {len(rows)} full-body articles, {count} requests.')

if __name__=='__main__': main()
