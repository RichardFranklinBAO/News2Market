"""Automatic third-party news discovery and cautious extraction.

One-command discovery: Google News RSS + Bing News RSS + publisher feeds.
No user-curated article URLs, no GDELT dependency, no paid API.
No authentication bypass, CAPTCHA bypass, rotating identities or paywall circumvention.

Run (Mac Terminal, inside the News2Market project):
    python scripts/news_feed_discovery.py --ticker NVDA --query NVIDIA --days 30 --max-external 5

Outputs a NEW Results/<ticker>/ExternalAuto/<run_id>/ directory. Does not change LATEST.txt.
Only extracted full article bodies count as full-text news. RSS summaries are metadata only.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html as htmlmod
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse, parse_qsl

import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

UA = 'News2MarketResearch/2.2.7 (+academic research; RSS discovery, respectful access)'
MAX_FEED_BYTES = 1_500_000
DEFAULT_FEEDS = [
    ('GoogleNews_Search', 'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US%3Aen'),
    ('BingNews_Search', 'https://www.bing.com/news/search?q={query}&format=rss&setmkt=en-US'),
    ('TechCrunch_AI', 'https://techcrunch.com/category/artificial-intelligence/feed/'),
    ('TechCrunch_Top', 'https://techcrunch.com/feed/'),
    ('CNBC_Tech', 'https://www.cnbc.com/id/19854910/device/rss/rss.html'),
    ('CNBC_Finance', 'https://www.cnbc.com/id/10000664/device/rss/rss.html'),
    ('ArsTechnica', 'https://feeds.arstechnica.com/arstechnica/index'),
    ('TheVerge', 'https://www.theverge.com/rss/index.xml'),
]
CANDIDATE_FIELDS = ['title','url','publisher','feed','published_date','date_quality',
                    'summary','eligible_for_body','extraction_note','original_feed_link']
ARTICLE_FIELDS = ['article_id','company','source','source_type','title','url','published_date',
                  'published_time_quality','text','text_chars','retrieved_utc',
                  'synthetic','extraction_strategy','extraction_paragraphs']
AUDIT_FIELDS = ['title','url','feed','publisher','status','reason','text_chars','feed_date','page_meta_date']


def write_csv(path, data, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)


def local_name(tag):
    return tag.split('}')[-1].lower()


def child_text(parent, names):
    for child in list(parent):
        if local_name(child.tag) in names:
            return ''.join(child.itertext()).strip()
    return ''


def clean_snippet(value):
    value = re.sub(r'<[^>]+>', ' ', htmlmod.unescape(value or ''))
    return re.sub(r'\s+', ' ', value).strip()[:700]


def item_date(raw):
    if not raw:
        return ''
    try:
        d = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try:
            d = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            return ''
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).date().isoformat()


def parse_feed(raw: bytes, feed_name: str):
    """Read both RSS items and Atom entries. No external entity processing."""
    root = ET.fromstring(raw)
    items = [e for e in root.iter() if local_name(e.tag) in ('item','entry')]
    rows = []
    for item in items:
        title = clean_snippet(child_text(item, {'title'}))
        pubdate = item_date(child_text(item, {'pubdate','published','updated','date'}))
        summary = clean_snippet(child_text(item, {'description','summary','content'}))
        publisher = child_text(item, {'source'}) or feed_name
        link = child_text(item, {'link'})
        if not link:
            for ch in list(item):
                if local_name(ch.tag) == 'link' and ch.attrib.get('href'):
                    if ch.attrib.get('rel', 'alternate') == 'alternate':
                        link = ch.attrib['href']; break
        link = htmlmod.unescape(link.strip())
        if title and link:
            rows.append({'title': title, 'url': link, 'publisher': publisher,
                         'feed': feed_name, 'published_date': pubdate,
                         'date_quality': 'RSS_date_not_page_verified' if pubdate else 'missing_RSS_date',
                         'summary':summary, 'original_feed_link':link})
    return rows


def extract_bing_publisher_link(url):
    p = urlparse(url)
    if p.hostname not in {'www.bing.com','bing.com'} or not p.path.startswith('/news/'):
        return url
    candidate = parse_qs(p.query).get('url', [''])[0]
    if candidate.startswith('https://'):
        return candidate
    return url


def clean_canonical(url):
    p = urlparse(url)
    # Remove tracking parameters; preserve meaningful publisher query parameters.
    drop = {'utm_source','utm_medium','utm_campaign','utm_content','utm_term',
            'fbclid','gclid','ref','ref_src','ocid'}
    kept = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
            if k.lower() not in drop and not k.lower().startswith('utm_')]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/', '', urlencode(kept), ''))


def is_relevant(title, summary, query):
    variants = [query.strip().lower()]
    if 'nvidia' in variants[0] or variants[0] == 'nvda':
        variants.extend(['nvidia','nvda'])
    text = (title+' '+summary).casefold()
    return any(re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)', text)
               for word in variants if len(word) >= 4)


def publisher_host(url):
    return (urlparse(url).hostname or '').lower()


def candidate_extraction_note(url):
    host = publisher_host(url)
    if host in {'news.google.com','www.google.com','google.com'}:
        return 'google_news_aggregator_link_unresolved_metadata_only'
    if host in {'www.bing.com','bing.com'}:
        return 'bing_wrapper_without_publisher_url_metadata_only'
    if any(host == d or host.endswith('.'+d) for d in ('nvidia.com','sec.gov','gdeltproject.org')):
        return 'first_party_or_noneditorial_metadata_only'
    if not url.startswith('https://'):
        return 'not_https_metadata_only'
    return ''


def bounded_get_xml(session, url, timeout=18):
    """One request per feed; fail closed on HTTP 429/403; no immediate retry."""
    resp = session.get(url, timeout=timeout, stream=True, allow_redirects=False,
                       headers={'User-Agent':UA, 'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    try:
        if resp.status_code == 429:
            return None, 'HTTP_429_rate_limited; respect_retry_after='+resp.headers.get('Retry-After','unspecified')
        if resp.status_code in (401,403):
            return None, f'HTTP_{resp.status_code}_access_restricted'
        if resp.status_code in (301,302,303,307,308):
            return None, 'feed_redirect_not_followed; provider_feed_url_may_have_changed'
        if resp.status_code != 200:
            return None, f'HTTP_{resp.status_code}'
        data = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            data.extend(chunk)
            if len(data) > MAX_FEED_BYTES:
                return None, 'feed_too_large'
        if not data.lstrip().startswith((b'<?xml',b'<rss',b'<feed',b'<rdf:RDF',b'<RDF')):
            return None, 'not_xml_or_unsupported_format'
        return bytes(data), ''
    finally:
        resp.close()


def page_date(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all('meta'):
        key = (tag.get('property') or tag.get('name') or tag.get('itemprop') or '').lower()
        if key in {'article:published_time','datepublished','pubdate','parsely-pub-date', 'dc.date.issued'}:
            hit = re.match(r'20\d{2}-\d{2}-\d{2}', tag.get('content') or '')
            if hit:
                return hit.group(0)
    for tag in soup.find_all('time'):
        hit = re.match(r'20\d{2}-\d{2}-\d{2}', tag.get('datetime') or '')
        if hit:
            return hit.group(0)
    return ''


def original_fetcher_module():
    path = SCRIPTS / 'external_article_fetcher.py'
    if not path.exists():
        raise RuntimeError('Missing existing scripts/external_article_fetcher.py; reinstall the complete News2Market repository')
    spec = importlib.util.spec_from_file_location('n2m_external_extractor',path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover(feeds, query, start, end, *, session, max_candidates=100, sleep_fn=time.sleep):
    found = []
    feed_audit = []
    unavailable_feed_hosts = set()
    window_days = max(1, min(90, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days + 1))
    for i, (name, template) in enumerate(feeds):
        if i:
            sleep_fn(1.0)
        url = template.replace('{query}', quote(query+f' when:{window_days}d', safe='')) if name=='GoogleNews_Search' else template.replace('{query}', quote(query, safe=''))
        entry = {'source':name,'status':'','items_in_feed':0,'matched':0,'error':'','url':url}
        feed_host=publisher_host(url)
        if feed_host in unavailable_feed_hosts:
            entry['status']='skipped';entry['error']='same_feed_host_previously_rate_limited_or_restricted'
            feed_audit.append(entry)
            continue
        try:
            blob, reason = bounded_get_xml(session, url)
            if reason:
                entry['status']='unavailable';entry['error']=reason
                if reason.startswith(('HTTP_429','HTTP_401','HTTP_403')):
                    unavailable_feed_hosts.add(feed_host)
                print(f'[News2Market] {name}: {reason}',flush=True)
                feed_audit.append(entry)
                continue
            records = parse_feed(blob, name)
            entry['items_in_feed']=len(records)
            for item in records:
                if not is_relevant(item['title'], item['summary'], query):
                    continue
                date = item['published_date']
                if not date or not (start <= date <= end):
                    continue
                if name == 'BingNews_Search':
                    item['url'] = extract_bing_publisher_link(item['url'])
                item['url'] = clean_canonical(item['url'])
                item['extraction_note'] = candidate_extraction_note(item['url'])
                item['eligible_for_body'] = 'no' if item['extraction_note'] else 'yes'
                found.append(item)
                entry['matched']+=1
            entry['status']='ok'
            print(f'[News2Market] {name}: {entry["matched"]} relevant links',flush=True)
        except (ET.ParseError,requests.RequestException,ValueError) as exc:
            entry['status']='error';entry['error']=f'{type(exc).__name__}: {str(exc)[:240]}'
            print(f'[News2Market] {name}: {entry["error"]}',flush=True)
        feed_audit.append(entry)
    # Keep independently discovered external links; de-duplicate by publisher URL and normalized title.
    seen_urls=set();seen_titles=set(); unique=[]
    for row in sorted(found,key=lambda r:(r['eligible_for_body']=='yes',r['published_date']),reverse=True):
        key_url = row['url'].rstrip('/').casefold()
        key_title = re.sub(r'[^a-z0-9]+','',row['title'].lower())[:160]
        if key_url in seen_urls or key_title in seen_titles:
            continue
        seen_urls.add(key_url);seen_titles.add(key_title)
        unique.append(row)
        if len(unique)>=max_candidates:
            break
    return unique,feed_audit


def extract_articles(rows, ticker, limit, *, use_env_proxy=False, fetcher=None, extractor=None):
    mod = original_fetcher_module() if fetcher is None or extractor is None else None
    if fetcher is None:
        fetcher=mod.CautiousFetcher(delay=2.0,timeout=18)
        fetcher.session.trust_env=use_env_proxy
    if extractor is None:
        from trafilatura import extract as extractor
    articles=[];audits=[];domain_counts={};blocked_hosts=set()
    for row in rows:
        if len(articles)>=limit:
            break
        url=row['url'];host=publisher_host(url)
        report={'title':row['title'],'url':url,'feed':row['feed'],'publisher':row['publisher'],
                'status':'','reason':'','text_chars':'','feed_date':row['published_date'], 'page_meta_date':''}
        if row['eligible_for_body']!='yes':
            report['status']='metadata_only';report['reason']=row['extraction_note']
        elif host in blocked_hosts:
            report['status']='skipped';report['reason']='provider_previously_blocked_or_rate_limited'
        elif domain_counts.get(host,0)>=2:
            report['status']='skipped';report['reason']='per_publisher_cap_2'
        else:
            try:
                # Existing CautiousFetcher re-checks global IPs, robots.txt and redirects.
                page,final_url = fetcher.get_html(url)
                body = re.sub(r'\s+', ' ', extractor(page,include_comments=False,favor_precision=True) or '').strip()
                if len(body)<350:
                    raise RuntimeError('body_too_short; RSS summary not substituted')
                actual_date=page_date(page)
                report['page_meta_date']=actual_date
                if actual_date and actual_date!=row['published_date']:
                    quality='DATE_MISMATCH_MANUAL_REVIEW'
                elif actual_date:
                    quality='page_meta_date_agrees_with_RSS_date'
                else:
                    quality='RSS_date_only_unverified'
                articles.append({'article_id':hashlib.sha256(final_url.encode()).hexdigest()[:20],
                    'company':ticker,'source':publisher_host(final_url),
                    'source_type':'third_party_rss_auto_discovered_unverified',
                    'title':row['title'],'url':final_url,
                    'published_date':row['published_date'], 'published_time_quality':quality,
                    'text':body[:16000], 'text_chars':min(len(body),16000),
                    'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                    'synthetic':False,'extraction_strategy':'rss_discovery_trafilatura_precision',
                    'extraction_paragraphs':''})
                domain_counts[host]=domain_counts.get(host,0)+1
                report['status']='extracted';report['text_chars']=len(body)
            except Exception as exc:
                report['status']='not_extracted';report['reason']=f'{type(exc).__name__}: {str(exc)[:200]}'
                if any(flag in str(exc).lower() for flag in ('http 429','http 403','http 401','robots.txt','robots unavailable')):
                    blocked_hosts.add(host)
        audits.append(report)
        print(f'[News2Market] article: {report["status"]} | {row["title"][:65]}',flush=True)
    return articles, audits


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ticker',default='NVDA')
    parser.add_argument('--query',default='NVIDIA',help='Company name for automatic search; not an article URL')
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--start',default=None,help='Optional YYYY-MM-DD; inclusive')
    parser.add_argument('--end',default=None,help='Optional YYYY-MM-DD; inclusive')
    parser.add_argument('--max-external',type=int,default=5)
    parser.add_argument('--max-candidates',type=int,default=80)
    parser.add_argument('--use-env-proxy',action='store_true',help='Honor YOUR preconfigured HTTPS_PROXY for connectivity, not for evading site access controls')
    parser.add_argument('--discover-only',action='store_true',help='Only discover metadata, do not fetch publisher article text')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,11}',args.ticker.upper()):parser.error('Invalid ticker')
    if not 1<=args.days<=90:parser.error('days must be 1..90')
    if not 1<=args.max_external<=20:parser.error('max-external must be 1..20')
    if not 1<=args.max_candidates<=200:parser.error('max-candidates must be 1..200')
    if not 2<=len(args.query.strip())<=100:parser.error('query length must be 2..100')
    today=datetime.now(timezone.utc).date()
    start=args.start or (today-timedelta(days=args.days)).isoformat()
    end=args.end or today.isoformat()
    if start>end:parser.error('start must be before end')
    if args.start and args.end:
        datetime.fromisoformat(args.start);datetime.fromisoformat(args.end)
    base=ROOT/'Results'/args.ticker.upper()/'ExternalAuto'
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run=base/run_id
    run.mkdir(parents=True,exist_ok=False)
    session=requests.Session()
    session.trust_env=args.use_env_proxy
    candidates,feed_audit=discover(DEFAULT_FEEDS,args.query,start,end,session=session,max_candidates=args.max_candidates)
    write_csv(run/'15_external_candidates.csv',candidates,CANDIDATE_FIELDS)
    if args.discover_only:
        articles=[];attempts=[]
    else:
        try:
            articles,attempts=extract_articles(candidates,args.ticker.upper(),args.max_external,use_env_proxy=args.use_env_proxy)
        except ImportError as exc:
            raise RuntimeError('Install optional free extractor: python -m pip install trafilatura') from exc
    write_csv(run/'15_external_articles.csv',articles,ARTICLE_FIELDS)
    write_csv(run/'15_external_article_audit.csv',attempts,AUDIT_FIELDS)
    audit={'version':'News2Market_v2.2.7_autoRSS','run':str(run),'ticker':args.ticker.upper(),
        'query':args.query,'date_window':[start,end], 'feed_audit':feed_audit,
        'feed_sources_attempted':len(feed_audit),
        'working_feeds':sum(r['status']=='ok' for r in feed_audit),
        'unique_relevant_links':len(candidates),'publisher_extraction_attempted':sum(r['status'] in ('extracted','not_extracted') for r in attempts),
        'full_text_extracted':len(articles),'articles_metadata_only':sum(r['status']=='metadata_only' for r in attempts),
        'no_GDELT_dependency':True,'no_hardcoded_article_urls':True,'did_not_modify_LATEST':True,
        'notes':['RSS dates and page dates are not independently verified timestamps of first market availability.',
                 'Google News aggregation links may be metadata-only and are never mistaken for publisher bodies.',
                 'Existing CautiousFetcher respects robots.txt, HTTPS, and site restrictions; not a paywall bypass.',
                 'A restricted or failing provider does not imply the story does not exist.',
                 'Do not merge these articles automatically into prior NVDA return regression.']}
    (run/'15_external_summary.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'\n[News2Market] AUTO COMPLETE: discovered={len(candidates)}, extracted={len(articles)}, working_feeds={audit["working_feeds"]}/{len(feed_audit)}')
    print(f'[News2Market] Files: {run}')
    print('[News2Market] Historical Results/NVDA/LATEST.txt unchanged.')

if __name__=='__main__':main()
