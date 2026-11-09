"""Collect HTML text from NVIDIA newsroom, checking robots.txt (fail closed)."""
from __future__ import annotations
import argparse
import hashlib
import re
import time
from datetime import date, datetime
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from scripts.shared.common import INPUTS, RESULTS, config, clean_text, message, read_csv, write_csv, json_dump

MONTH_RE = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
DATE_RE = re.compile(rf'\b{MONTH_RE}\s+\d{{1,2}},\s+20\d{{2}}\b')
FIELDS = ['article_id','company','source','source_type','title','url','published_date',
          'published_time_quality','text','text_chars','retrieved_utc','synthetic','extraction_strategy','extraction_paragraphs']


def extract_archive_candidates(html: str, base_url: str):
    """Parse archive title links and nearby printed dates, not guessed dates."""
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    seen = set()
    for h in soup.select('h3'):
        anchor = h.find('a', href=True)
        if not anchor:
            continue
        url = urljoin(base_url, anchor['href']).split('#')[0]
        parsed = urlparse(url)
        if parsed.netloc != 'nvidianews.nvidia.com' or not parsed.path.startswith('/news/'):
            continue
        if url in seen:
            continue
        # The nearest preceding visible date is more reliable than scanning a whole parent.
        previous = h.find_previous(string=lambda value: bool(value and DATE_RE.search(str(value))))
        date_string = DATE_RE.search(str(previous)).group(0) if previous else None
        if not date_string:
            continue
        published = datetime.strptime(date_string, '%B %d, %Y').date().isoformat()
        title = clean_text(anchor.get_text(' ', strip=True))
        if not title or title.lower() in {'read press release', 'read blog'}:
            continue
        result.append({'title': title, 'url': url, 'published_date': published})
        seen.add(url)
    return result


def extract_article_text_with_audit(html: str):
    """Extract article prose, not site navigation or a short SEO description.

    v1.0 selected the *first* <article> even if that node was an empty/related
    story card. Here we check several likely containers and compare the actual
    prose they contain. No artificial fallback to title or metadata is allowed.
    """
    soup = BeautifulSoup(html, 'html.parser')
    # Some news sites put metadata inside <header> and body elsewhere; do not
    # limit extraction to the first <article> element.
    for tag in soup.select('script, style, nav, footer, noscript, form, aside'):
        tag.decompose()

    selectors = [
        '[itemprop="articleBody"]', '.article-body', '.article__body',
        '.press-release-body', '.release-body', '.field--name-body',
        '.body-copy', '.content-body', '.story-body', '.news-body',
        '.node__content', 'main', '[role="main"]', 'article', 'body'
    ]
    candidates = []
    seen_roots = set()
    for selector in selectors:
        for root in soup.select(selector)[:20]:
            if id(root) in seen_roots:
                continue
            seen_roots.add(id(root))
            paragraphs = []
            seen_lines = set()
            for tag in root.find_all(['h2', 'h3', 'p', 'li']):
                line = clean_text(tag.get_text(' ', strip=True))
                if re.match(r'^(About NVIDIA|Media Contacts|Forward-Looking Statements|Downloads|More News)$', line, re.I):
                    if paragraphs:
                        break
                    continue
                if tag.name not in ('p', 'li') or len(line) < 35:
                    continue
                if line.lower().startswith(('privacy policy', 'cookie settings', 'all rights reserved')):
                    continue
                if line not in seen_lines:
                    paragraphs.append(line)
                    seen_lines.add(line)
            # Some publisher layouts use nested <div> blocks without <p>.
            # Only fall back to leaf-like blocks, not every parent node.
            if not paragraphs:
                for block in root.find_all(['div', 'section']):
                    if block.find(['div', 'section', 'p', 'li']):
                        continue
                    line = clean_text(block.get_text(' ', strip=True))
                    if 80 <= len(line) <= 2000 and line not in seen_lines:
                        paragraphs.append(line)
                        seen_lines.add(line)
            text = '\n'.join(paragraphs)[:16000]
            if text:
                # Long news prose with multiple paragraphs is more trustworthy
                # than an empty <article> or a promotional teaser.
                candidates.append((len(text), len(paragraphs), selector, text))
    if not candidates:
        return '', {'strategy':'none', 'paragraphs':0, 'candidate_roots':len(seen_roots)}
    # Content-first selection: select strongest actual body, not first tag match.
    # A broader container can include related stories, so the output still
    # requires manual review prior to economic claims.
    candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
    length, n, selector, text = candidates[0]
    return text, {'strategy':selector,'paragraphs':n, 'candidate_roots':len(seen_roots),
                  'extracted_chars':length}


def extract_article_text(html: str):
    """Backward-compatible text-only wrapper for tests and other callers."""
    return extract_article_text_with_audit(html)[0]


def extraction_diagnostics(html: str):
    """Small, non-sensitive summary when a fetched page has no usable prose."""
    soup=BeautifulSoup(html,'html.parser')
    title=soup.title.get_text(' ',strip=True)[:100] if soup.title else '(no HTML title)'
    paragraphs=soup.find_all('p')
    return {'html_bytes_approx':len(html.encode('utf-8')),
            'page_title':title,
            'paragraph_tags':len(paragraphs),
            'long_paragraph_tags':sum(len(clean_text(p.get_text(' ',strip=True)))>=35 for p in paragraphs),
            'article_elements':len(soup.select('article')),
            'main_elements':len(soup.select('main')),
            'visible_text_chars':len(clean_text(soup.get_text(' ',strip=True)))}


class PoliteFetcher:
    def __init__(self, cfg):
        self.cfg = cfg
        self.s = requests.Session()
        self.ua = cfg['user_agent']
        self.s.headers.update({'User-Agent': self.ua, 'Accept': 'text/html,application/xhtml+xml'})
        self.robots = {}
        self.last_request = 0.
        self.count = 0

    def check_robots(self, url):
        host = urlparse(url).netloc
        if host not in self.robots:
            robots_url = f'{urlparse(url).scheme}://{host}/robots.txt'
            try:
                r = self.s.get(robots_url, timeout=self.cfg['timeout_seconds'])
                self.count += 1
                r.raise_for_status()
                self.last_request = time.monotonic()
                if not re.search(r'(?im)^\s*user-agent\s*:', r.text):
                    raise RuntimeError('Invalid robots.txt: no User-agent directive; refusing to infer permission')
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(r.text.splitlines())
                self.robots[host] = parser
            except Exception as e:
                raise RuntimeError(f'Cannot verify robots.txt at {robots_url}; stopping rather than assuming permission: {e}') from e
        if not self.robots[host].can_fetch(self.ua, url):
            raise RuntimeError(f'Robots.txt disallows this URL: {url}')

    def get(self, url):
        self.check_robots(url)
        parser = self.robots[urlparse(url).netloc]
        robots_delay = parser.crawl_delay(self.ua) or 0
        remaining = max(self.cfg['min_seconds_between_requests'], robots_delay) - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        try:
            r = self.s.get(url, timeout=self.cfg['timeout_seconds'], stream=True)
            self.last_request = time.monotonic()
            self.count += 1
            r.raise_for_status()
            if 'html' not in r.headers.get('content-type','').lower():
                raise RuntimeError(f'Expected HTML from {url}, got {r.headers.get("content-type")}')
            cap = self.cfg['max_page_bytes']
            raw = b''
            for part in r.iter_content(chunk_size=65536):
                raw += part
                if len(raw) > cap:
                    raise RuntimeError(f'HTML larger than max_page_bytes={cap}: {url}')
            r._content = raw
            return r.text
        finally:
            try:
                r.close()
            except UnboundLocalError:
                pass


def collect_live(cfg, max_articles):
    collect = cfg['collection']
    fetcher = PoliteFetcher(collect)
    start = date.fromisoformat(cfg['project']['start_date'])
    end = date.fromisoformat(cfg['project']['end_date'])
    if end >= date.today():
        message('Warning: end_date may include today; live pages can update after collection.')
    candidates = []
    urls = set()
    for page in range(1, collect['max_pages']+1):
        archive_url = collect['archive_url'].format(page=page)
        try:
            html = fetcher.get(archive_url)
        except Exception as e:
            if page == 1:
                raise
            message(f'Archive page {page} failed ({e}); continuing with pages already obtained.')
            break
        found = extract_archive_candidates(html, archive_url)
        if not found:
            message(f'No article title/date pairs found on archive page {page}. HTML layout may have changed.')
            break
        for item in found:
            d = date.fromisoformat(item['published_date'])
            if start <= d <= end and item['url'] not in urls:
                urls.add(item['url'])
                candidates.append(item)
        message(f'Archive page {page}: {len(found)} links, {len(candidates)} in target window.')
        # Stop once oldest dated record on page is earlier than requested start.
        if min(date.fromisoformat(x['published_date']) for x in found) < start:
            break
        if len(candidates) >= max_articles * 2:
            break
    rows = []
    retrieval_time = datetime.now().astimezone().isoformat()
    for item in candidates:
        if len(rows) >= max_articles:
            break
        try:
            article_html = fetcher.get(item['url'])
            text, extraction_audit = extract_article_text_with_audit(article_html)
            if len(text) < collect['min_article_chars']:
                message(f'Skipping very short body ({len(text)} chars): {item["url"]}; strategy={extraction_audit["strategy"]}; diagnostics={extraction_diagnostics(article_html)}')
                continue
            rows.append({
                'article_id': hashlib.sha256(item['url'].encode()).hexdigest()[:16],
                'company': 'NVIDIA CORPORATION',
                'source':'NVIDIA Newsroom',
                'source_type':'first_party_press_release',
                'title':item['title'], 'url':item['url'],
                'published_date':item['published_date'],
                'published_time_quality':'date_only_no_intraday_timestamp',
                'text':text, 'text_chars':len(text),
                'retrieved_utc':retrieval_time, 'synthetic':False,
                'extraction_strategy':extraction_audit['strategy'],
                'extraction_paragraphs':extraction_audit['paragraphs']})
        except Exception as e:
            message(f'Article fetch skipped: {item["url"]}: {e}')
    if not rows:
        raise RuntimeError('No real article bodies collected. Check robots.txt, date range, page layout, and site access. Not silently switching to demo.')
    return rows, fetcher.count


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['demo','live'], required=True)
    p.add_argument('--max-articles', type=int, default=None)
    args = p.parse_args()
    cfg = config()
    max_articles = args.max_articles or cfg['collection']['max_articles']
    if not 1 <= max_articles <= 50:
        raise ValueError('Safety limit: --max-articles must be between 1 and 50')
    if args.mode == 'demo':
        rows = read_csv(INPUTS / 'demo_articles.csv')[:max_articles]
        if not rows:
            raise RuntimeError('Missing synthetic test fixture; supply a locally generated offline fixture if needed.')
        fetch_count = 0
    else:
        rows, fetch_count = collect_live(cfg, max_articles)
    write_csv(RESULTS / '01_articles.csv', rows, FIELDS)
    json_dump(RESULTS / '01_collection_audit.json', {
        'mode':args.mode, 'articles_kept':len(rows), 'network_requests':fetch_count,
        'date_only':True, 'first_party_source_bias':True,
        'max_articles':max_articles,
        'warning':'Demo observations are synthetic; live source is corporate communications, NOT independent journalism.'})
    message(f'Collected {len(rows)} records (mode={args.mode}, HTTP requests={fetch_count}).')

if __name__ == '__main__':
    main()
