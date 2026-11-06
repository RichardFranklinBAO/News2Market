"""Opt-in, low-volume external web article extraction from GDELT discovery links.

No promise of whole-Internet coverage. No paywall bypass. Fail closed on robots errors.
This feature is experimental, not independently verified live.
"""
from __future__ import annotations
import hashlib,ipaddress,json,re,socket,time
from collections import Counter
from datetime import datetime,timezone
from urllib.parse import urlparse,urljoin
from urllib.robotparser import RobotFileParser
import requests
from common import RESULTS,config,read_csv,write_csv,json_dump,message,clean_text
from nvidia_scraper import FIELDS

USER_AGENT='News2MarketResearch/2.2 (academic pilot; respectful crawling)'
BLOCKED_SUFFIXES=('.pdf','.zip','.exe','.doc','.docx','.ppt','.pptx','.mp4','.mp3')


def public_http_url(url):
    try:
        p=urlparse(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):return False
        if p.hostname.lower() in ('localhost','localhost.localdomain') or p.hostname.endswith('.local'):return False
        if p.path.lower().endswith(BLOCKED_SUFFIXES):return False
        addrs=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
        return bool(addrs) and all(ipaddress.ip_address(t[4][0]).is_global for t in addrs)
    except (ValueError,OSError):return False


def is_relevant_title(title,company,ticker):
    text=title.casefold()
    name=company.casefold().replace('corporation','').replace('incorporated','').replace('inc.','').strip()
    variants=[name]
    if name.startswith('nvidia'):variants+=['nvidia']
    # Avoid matching short, ambiguous ticker strings such as CAT, ALL, IT.
    if len(ticker)>=4:variants += [ticker.casefold()]
    return any(re.search(r'(?<!\w)'+re.escape(v)+r'(?!\w)',text) for v in variants if v and len(v)>=4)


class CautiousFetcher:
    def __init__(self,delay=2.0,timeout=15):
        self.session=requests.Session();self.session.trust_env=False
        self.session.headers.update({'User-Agent':USER_AGENT,'Accept':'text/html,application/xhtml+xml'})
        self.robots={};self.last={};self.delay=delay;self.timeout=timeout
        self.count=0

    def robots_ok(self,url):
        p=urlparse(url);root=f'https://{p.netloc}'
        if root not in self.robots:
            resp=self.session.get(root+'/robots.txt',allow_redirects=False,timeout=self.timeout)
            self.count+=1
            if resp.status_code==404:
                rp=RobotFileParser();rp.parse([])
            elif resp.status_code==200 and len(resp.content)<500_000:
                rp=RobotFileParser();rp.parse(resp.text.splitlines())
            else:
                raise RuntimeError(f'robots unavailable or blocked ({resp.status_code})')
            self.robots[root]=rp
        return self.robots[root].can_fetch(USER_AGENT,url)

    def get_html(self,url):
        for _ in range(3):
            if not public_http_url(url): raise RuntimeError('non-public or unsafe URL')
            if not self.robots_ok(url): raise RuntimeError('robots.txt denies URL')
            host=urlparse(url).netloc
            time.sleep(max(0.0,self.delay-(time.monotonic()-self.last.get(host,0))))
            self.last[host]=time.monotonic()
            r=self.session.get(url,timeout=self.timeout,allow_redirects=False,stream=True)
            self.count+=1
            if r.status_code in (301,302,303,307,308):
                url=urljoin(url,r.headers.get('Location',''))
                r.close();continue
            if r.status_code in (401,403,429):raise RuntimeError(f'HTTP {r.status_code}: restricted')
            r.raise_for_status()
            if 'text/html' not in r.headers.get('Content-Type','').lower():raise RuntimeError('not HTML')
            body=bytearray()
            for chunk in r.iter_content(chunk_size=65536):
                body.extend(chunk)
                if len(body)>2_000_000:raise RuntimeError('HTML > 2MB')
            return body.decode(r.encoding or 'utf-8',errors='replace'),url
        raise RuntimeError('too many redirects')


def gdelt_seen_date(raw):
    s=re.sub(r'[^0-9]','',raw or '')
    if len(s)<8:return ''
    try:return datetime.strptime(s[:8],'%Y%m%d').date().isoformat()
    except ValueError:return ''


def main():
    cfg=config();ctx=cfg['_context']
    enabled=(ctx['mode']=='live' and bool(ctx.get('web_news')))
    candidates=read_csv(RESULTS/'01_gdelt_metadata_only.csv')
    out=[];fail=[];count=0
    if enabled:
        try: from trafilatura import extract
        except ImportError as e:raise RuntimeError('Install free dependency: python -m pip install trafilatura') from e
        f=CautiousFetcher(delay=max(2.0,cfg['collection']['min_seconds_between_requests']))
        company=__import__('json').loads((RESULTS/'00_company.json').read_text(encoding='utf-8'))['name']
        ticker=cfg['project']['ticker']
        host_counts=Counter()
        for item in candidates[:50]:
            if len(out)>=ctx.get('max_external',10):break
            url=item.get('url','');title=item.get('title','').strip();hostname=urlparse(url).hostname or ''
            if host_counts[hostname]>=2:continue
            if not is_relevant_title(title,company,ticker):
                fail.append({'url':url,'reason':'company not clearly mentioned in title'});continue
            if 'nvidianews.nvidia.com' in hostname or 'sec.gov' in hostname:
                fail.append({'url':url,'reason':'official sources handled separately'});continue
            if not gdelt_seen_date(item.get('seen_date','')):
                fail.append({'url':url,'reason':'no GDELT seen date'});continue
            if not public_http_url(url):
                fail.append({'url':url,'reason':'invalid or non-public HTTPS URL'});continue
            try:
                html,final_url=f.get_html(url)
                text=clean_text(extract(html,include_comments=False,favor_precision=True) or '')
                if len(text)<250:raise RuntimeError('no reliable full body')
                date=gdelt_seen_date(item.get('seen_date',''))
                if not cfg['project']['start_date']<=date<=cfg['project']['end_date']:
                    raise RuntimeError('GDELT first-seen date outside window')
                out.append({'article_id':hashlib.sha256(final_url.encode()).hexdigest()[:20],
                  'company':ticker,'source':urlparse(final_url).netloc,
                  'source_type':'external_web_unverified','title':title,'url':final_url,
                  'published_date':date,'published_time_quality':'GDELT_first_seen_DATE_PROXY_not_verified_publication',
                  'text':text[:16000],'text_chars':min(len(text),16000),
                  'retrieved_utc':datetime.now(timezone.utc).isoformat(),'synthetic':False,
                  'extraction_strategy':'trafilatura_precision','extraction_paragraphs':''})
                host_counts[hostname]+=1
            except Exception as exc:
                fail.append({'url':url,'reason':str(exc)[:200]})
        count=f.count
    write_csv(RESULTS/'03b_external_articles.csv',out,FIELDS)
    json_dump(RESULTS/'03b_external_audit.json',{
      'enabled':enabled,'links_discovered':len(candidates),'full_text_count':len(out),
      'http_requests_including_robots':count,'attempts_failed_or_filtered':fail,
      'warning':'GDELT first-seen used as conservative DATE PROXY; not a verified publication timestamp. External_web_unverified may include syndication and promotional content. Manual legal/quality review is needed. Extraction not verified online.'})
    message(f'External web full bodies: {len(out)}; {count} HTTP requests; optional={enabled}.')

if __name__=='__main__':main()
