"""Respectful SEC EDGAR submission retrieval for US-listed issuers.

SEC: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Requires a user-declared identification and contact. Access denials/rate limits are
not retried or circumvented. Publication/acceptance timestamps are not certified
market-availability timestamps.
"""
from __future__ import annotations
import hashlib
import html
import re
import time
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SEC_BASE = "https://data.sec.gov"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
FORMS = frozenset({"8-K", "10-Q", "10-K"})
MAX_BODY_BYTES = 1_500_000
MAX_TEXT_CHARS = 240_000


class SecAccessError(RuntimeError):
    pass


def valid_agent(agent: str) -> bool:
    agent = (agent or "").strip()
    return len(agent) >= 12 and "@" in agent and not re.search(r"[\r\n]", agent)


class SecClient:
    """A deliberately slow, identifiable SEC client (<=2 requests/second)."""
    def __init__(self, agent: str, session=None, delay=0.6):
        if not valid_agent(agent):
            raise ValueError("SEC access requires --sec-user-agent with your name and real contact email")
        self.session = session if session is not None else requests.Session()
        self.headers = {"User-Agent": agent.strip(), "Accept-Encoding": "gzip, deflate", "Accept": "application/json,text/html"}
        self.delay = max(0.5, float(delay))
        self.last_request = None
        self.requests_made = 0

    def get(self, url: str, max_bytes: int = MAX_BODY_BYTES) -> tuple[bytes, dict]:
        host = urlparse(url).hostname
        if host not in {"data.sec.gov", "www.sec.gov"} or not url.startswith("https://"):
            raise ValueError("Refusing non-SEC URL")
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.requests_made += 1
        try:
            response = self.session.get(url, headers=self.headers, timeout=25, stream=True, allow_redirects=False)
        except requests.RequestException as e:
            raise SecAccessError(f"SEC request failed ({type(e).__name__})") from e
        try:
            if response.status_code in (403, 429):
                raise SecAccessError(f"SEC returned HTTP {response.status_code}; stop and consult SEC fair-access guidance")
            if response.status_code in (301,302,303,307,308):
                raise SecAccessError("SEC returned a redirect; automatic following is disabled")
            if response.status_code != 200:
                raise SecAccessError(f"SEC returned HTTP {response.status_code}")
            if not (1 <= int(max_bytes) <= 20_000_000):
                raise ValueError('Unsafe SEC response byte cap')
            chunks=[];total=0;truncated=False
            for chunk in response.iter_content(chunk_size=64*1024):
                if not chunk:continue
                remaining=max_bytes-total
                if len(chunk)>remaining:
                    if remaining:chunks.append(chunk[:remaining])
                    total+=max(0,remaining)
                    truncated=True
                    break
                chunks.append(chunk);total+=len(chunk)
            raw=b"".join(chunks)
            return raw, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes":len(raw),
                         "truncated":truncated, "content_type":response.headers.get("Content-Type","")}
        finally:
            response.close()

    def submissions(self,cik:str):
        cik_number=str(int(cik)).zfill(10)
        raw,meta = self.get(f"{SEC_BASE}/submissions/CIK{cik_number}.json", max_bytes=10_000_000)
        if meta['truncated']:
            raise SecAccessError('SEC submissions JSON exceeded local byte cap; refusing partial metadata')
        import json
        try:
            data=json.loads(raw)
        except (ValueError,UnicodeError) as e:
            raise SecAccessError("SEC submission response was not valid JSON") from e
        if not isinstance(data,dict) or "filings" not in data:
            raise SecAccessError("SEC submission JSON missing filings metadata")
        if 'cik' in data and str(int(data['cik']))!=str(int(cik_number)):
            raise SecAccessError('SEC response CIK does not match requested issuer')
        return data


def _filing_url(cik:str, accession:str, primary_document:str) -> str:
    accession=str(accession)
    primary_document=str(primary_document)
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}",accession):
        raise ValueError("Malformed SEC accession number")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}",primary_document) or ".." in primary_document:
        raise ValueError("Unsafe SEC primary document filename")
    return f"{ARCHIVES_BASE}/{int(cik)}/{accession.replace('-', '')}/{primary_document}"


def select_filings(submissions:dict, cik:str, from_date:str, to_date:str,
                   forms=FORMS, limit=15) -> list[dict]:
    """Filter the SEC 'filings.recent' arrays; do not pretend this is a full EDGAR archive."""
    start=date.fromisoformat(str(from_date));end=date.fromisoformat(str(to_date))
    if start>end:
        raise ValueError("start must be <= end")
    if not (1 <= int(limit) <= 100):
        raise ValueError("limit must be between 1 and 100")
    allowed=set(forms)
    if not allowed.issubset(FORMS):
        raise ValueError("Only 8-K, 10-Q and 10-K forms are supported")
    recent=submissions.get("filings",{}).get("recent",{})
    required=("accessionNumber","filingDate","form","primaryDocument")
    if any(not isinstance(recent.get(k),list) for k in required):
        raise ValueError("Malformed SEC recent filing arrays")
    n=min(len(recent[k]) for k in required)
    result=[];seen=set()
    for i in range(n):
        form=str(recent["form"][i]);filed=str(recent["filingDate"][i])
        if form not in allowed:
            continue
        try:
            filing_date=date.fromisoformat(filed)
        except ValueError:
            continue
        if not(start <= filing_date <= end):
            continue
        accession=str(recent["accessionNumber"][i]);primary=str(recent["primaryDocument"][i]);
        if accession in seen:
            continue
        try:
            url=_filing_url(cik,accession,primary)
        except ValueError:
            continue
        seen.add(accession)
        accepted=(recent.get("acceptanceDateTime",[])+[""]*n)[i]
        result.append({"article_id":f"SEC-{accession}","cik":str(int(cik)).zfill(10),
            "source":"SEC EDGAR", "source_type":"sec_filing_primary_document", "form":form,
            "published_date":filed,"accepted_datetime_raw":str(accepted),
            "published_time_quality":"SEC acceptance field; timezone/market availability not independently verified",
            "url":url,"accession":accession,"title":f"Form {form} ({filed})",
            "text":"", "text_status":"not_retrieved", "text_truncated":False,
            "text_sha256":""})
    result.sort(key=lambda x:(x["published_date"],x["accession"]),reverse=True)
    return result[:int(limit)]


def html_to_text(body:bytes, content_type:str="") -> str:
    ctype=content_type.lower()
    if "pdf" in ctype or body[:4]==b"%PDF":
        raise ValueError("PDF primary documents are not supported")
    text=body.decode("utf-8",errors="replace")
    if "<html" not in text[:1000].lower() and "<body" not in text[:1000].lower() and not re.search(r"<\w+\b",text[:1000]):
        return " ".join(html.unescape(text).split())
    soup=BeautifulSoup(text,"html.parser")
    for item in soup(["script","style","noscript","svg","head"]):
        item.decompose()
    return " ".join(soup.get_text(" ",strip=True).split())


def fetch_bodies(client:SecClient,filings:list[dict]) -> tuple[list[dict],list[dict]]:
    updated=[];issues=[]
    for original in filings:
        row=original.copy()
        if not row["url"].lower().endswith((".htm",".html",".txt")):
            row["text_status"]="unsupported_primary_document_extension"
            issues.append({'article_id':row['article_id'],'reason':'unsupported_primary_document_extension'})
        else:
            try:
                raw,meta=client.get(row["url"])
                content=html_to_text(raw,meta["content_type"])
                row['downloaded_bytes']=meta['bytes']
                row['raw_response_sha256']=meta['sha256']
                row['response_truncated']=bool(meta['truncated'])
                row['extracted_chars_before_cap']=len(content)
                row["text_truncated"]=bool(meta["truncated"] or len(content)>MAX_TEXT_CHARS)
                content=content[:MAX_TEXT_CHARS]
                row["text"]=content
                row["text_sha256"]=hashlib.sha256(content.encode()).hexdigest()
                row["text_status"]=('truncated' if row['text_truncated'] else
                    ('extracted' if len(content)>=100 else 'short_text'))
            except SecAccessError as e:
                row["text_status"]="access_denied_or_unavailable"
                issues.append({"article_id":row["article_id"],"reason":str(e)})
                updated.append(row)
                if "HTTP 403" in str(e) or "HTTP 429" in str(e):
                    # Do not keep requesting a provider which is limiting the user.
                    for remaining in filings[len(updated):]:
                        newrow=remaining.copy();newrow["text_status"]="not_attempted_after_access_limit";updated.append(newrow)
                    return updated,issues
                continue
            except (ValueError,UnicodeError) as e:
                row["text_status"]="unsupported_or_invalid_body"
                issues.append({"article_id":row["article_id"],"reason":str(e)[:160]})
        updated.append(row)
    return updated,issues
