"""News2Market: reproducible three-company research workbench.

Needs existing Scripts/ directory and locally installed official LM dictionary.
The reported price/return analysis is exploratory, not a trading model.
"""
from __future__ import annotations

import csv
import hashlib
import io
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "Scripts"
INPUTS = ROOT / "Inputs"
RESULTS = ROOT / "Results"
SCRIPT_NAMES = {"05_lm_sentiment.py", "11_prepare_text.py", "11b_lm_cleaned.py", "06_event_tags.py"}
BENCHMARK = "QQQ"
MODEL = "qwen2.5:1.5b"

# One profile is configuration, not a separate copy of the research pipeline.
COMPANIES = {
    "NVDA": {
        "name": "NVIDIA Corporation", "label": "NVIDIA", "query": "NVIDIA",
        "aliases": ["nvidia", "nvda", "geforce", "nvidia blackwell"],
        "official_feed": None, "official_host": "nvidianews.nvidia.com",
        "cik": "0001045810", "has_issuer_scraper": True,
    },
    "AAPL": {
        "name": "Apple Inc.", "label": "Apple", "query": "Apple",
        "aliases": ["apple", "aapl", "iphone", "ipad", "macbook", "apple intelligence"],
        "official_feed": "https://www.apple.com/newsroom/rss-feed.rss",
        "official_host": "apple.com", "cik": "0000320193", "has_issuer_scraper": False,
    },
    "GOOGL": {
        "name": "Alphabet Inc. (Google)", "label": "Google / Alphabet Class A", "query": "Google",
        "aliases": ["google", "alphabet", "googl", "deepmind", "google cloud"],
        "official_feed": "https://blog.google/rss/", "official_host": "blog.google",
        "cik": "0001652044", "has_issuer_scraper": False,
    },
}


def supported_companies():
    return [{"ticker": k, "name": v["label"], "company": v["name"]} for k, v in COMPANIES.items()]


def validate_options(ticker="NVDA", news_days=30, price_years=5, max_news=10,
                     price_mode="auto", use_proxy=False, local_llm=False):
    ticker = str(ticker).strip().upper()
    if ticker not in COMPANIES:
        raise ValueError("MVP currently supports only NVDA, AAPL and GOOGL (Alphabet Class A)")
    news_days = int(news_days); price_years = int(price_years); max_news = int(max_news)
    if news_days not in (14, 30, 60, 90):
        raise ValueError("news_days must be 14, 30, 60, or 90")
    if price_years not in (1, 3, 5):
        raise ValueError("price_years must be 1, 3, or 5")
    if max_news not in (5, 10, 15):
        raise ValueError("max_news must be 5, 10, or 15")
    if price_mode not in ("auto", "nasdaq_csv", "csv"):
        raise ValueError("price_mode must be auto or nasdaq_csv")
    if not isinstance(use_proxy, bool) or not isinstance(local_llm, bool):
        raise ValueError("use_proxy and local_llm must be true/false")
    return {"ticker": ticker, "news_days": news_days, "price_years": price_years,
            "max_news": max_news, "price_mode": price_mode, "use_proxy": use_proxy,
            "local_llm": local_llm}


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_day(d):
    return date.fromisoformat(str(d))


def subtract_years(d, years):
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def scripts_on_path():
    if not SCRIPTS.is_dir() or not (SCRIPTS / "lm_dictionary.py").exists():
        raise FileNotFoundError("Install addon in project ROOT alongside existing Scripts/ and Inputs/")
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))


def import_numeric_script(filename, module_name):
    scripts_on_path()
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot import existing script {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def financial_text_relevance(title, summary, profile):
    """Conservative lexical candidate filter; not research-grade entity resolution."""
    s = f"{title or ''} {summary or ''}".casefold()
    if not any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", s)
               for alias in profile["aliases"]):
        return False
    if profile["query"] == "Apple":
        # Exclude clear horticulture/food false positives from generic Apple keyword.
        if re.search(r"\b(apple pie|apple orchard|apple cider|apple harvest|apple tree|apple fruit|applesauce)\b", s) \
           and not re.search(r"\b(iphone|ipad|macbook|apple inc|aapl)\b", s):
            return False
    return True


def _host_matches(host, domain):
    host = (host or "").lower();domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def _candidate_filter(candidates, profile):
    accepted=[];excluded=[]
    for row in candidates:
        if financial_text_relevance(row.get("title"), row.get("summary"), profile):
            accepted.append(row)
        else:
            excluded.append({"title":row.get("title"), "reason":"entity_relevance_filter"})
    return accepted,excluded


def discover_news(profile, ticker, from_day, to_day, max_news, use_proxy=False, log=print):
    """News download: existing RSS/publisher extractor plus optional NVIDIA archive adapter."""
    scripts_on_path()
    rss = import_numeric_script("15_auto_external_news.py", "n2m_rss_collector")
    import requests

    collected=[];audit={"rss_feeds":[],"excluded_candidates":[],"nvidia_issuer_error":None,
                        "official_feed":profile["official_feed"]}
    if ticker == "NVDA":
        try:
            import copy
            import yaml
            from nvidia_scraper import collect_live
            cfg=yaml.safe_load((INPUTS/"config.yaml").read_text(encoding="utf-8"))
            cfg=copy.deepcopy(cfg)
            cfg["project"].update({"ticker": ticker, "start_date":from_day, "end_date":to_day})
            cfg["collection"]["max_pages"]=min(5, int(cfg["collection"].get("max_pages",5)))
            log("Collecting NVIDIA first-party announcements (independent of RSS)")
            original, count=collect_live(cfg, min(max_news,8))
            collected.extend(original)
            audit["nvidia_official_http_requests"]=count
        except Exception as exc:
            audit["nvidia_issuer_error"]=f"{type(exc).__name__}: {str(exc)[:300]}"
            log("NVIDIA issuer source unavailable; proceeding with RSS/news publishers")

    # Keep feed count modest on low-RAM / slow-network machines.
    feeds=[
      rss.DEFAULT_FEEDS[0],  # Google News Search (may time out, recorded)
      rss.DEFAULT_FEEDS[2],  # TechCrunch AI
      rss.DEFAULT_FEEDS[3],  # TechCrunch general
      rss.DEFAULT_FEEDS[4],  # CNBC Tech
      rss.DEFAULT_FEEDS[6],  # Ars Technica
    ]
    if profile["official_feed"]:
        feeds.insert(0,("Official_"+ticker,profile["official_feed"]))
    session=requests.Session();session.trust_env=use_proxy
    log(f"Finding {ticker} news via {len(feeds)} RSS sources, no article URL seeding")
    # Isolate each provider request, so the GUI can show actual progress if a feed stalls.
    candidates=[];feed_audit=[]
    for idx,feed in enumerate(feeds,1):
        if idx>1:time.sleep(1.0)
        log(f"RSS {idx}/{len(feeds)}: {feed[0]}")
        try:
            discovered,provider_audit=rss.discover([feed],profile["query"],from_day,to_day,
                         session=session,max_candidates=70)
            candidates.extend(discovered)
            feed_audit.extend(provider_audit)
        except Exception as exc:
            feed_audit.append({"source":feed[0],"status":"error",
                "error":f"{type(exc).__name__}: {str(exc)[:250]}"})
    # Normalize across provider feeds: preserve the best publisher URL, not the search wrapper.
    already_urls=set();already_titles=set();deduped=[]
    for row in sorted(candidates,key=lambda r:(r.get('eligible_for_body')=='yes',r.get('published_date','')),reverse=True):
        u=str(row.get('url','')).rstrip('/').lower()
        title_key=re.sub(r'[^a-z0-9]','',str(row.get('title','')).lower())[:160]
        if u in already_urls or title_key in already_titles:continue
        already_urls.add(u);already_titles.add(title_key);deduped.append(row)
    candidates=deduped[:70]
    audit["rss_feeds"]=feed_audit
    candidates,excluded=_candidate_filter(candidates,profile)
    audit["excluded_candidates"]=excluded
    seen_urls={str(r.get("url","")).rstrip("/").casefold() for r in collected}
    if len(collected) < max_news:
        fetched,fetch_audit=rss.extract_articles(candidates,ticker,max_news-len(collected),
                                                use_env_proxy=use_proxy)
        audit["publisher_extraction"]=fetch_audit
        for r in fetched:
            if str(r.get("url","")).rstrip("/").casefold() in seen_urls:
                continue
            seen_urls.add(str(r.get("url","")).rstrip("/").casefold())
            host=urlparse(r.get("url","")).hostname or ""
            official=_host_matches(host,profile["official_host"])
            r["source_type"]="first_party_press_release" if official else "third_party_rss_auto_discovered_unverified"
            r["company"]=profile["name"]
            collected.append(r)
    audit["qualified_articles"]=len(collected)
    audit["source_breakdown"]={
        "first_party":sum(r.get("source_type","").startswith("first_party") for r in collected),
        "third_party":sum(r.get("source_type","").startswith("third_party") for r in collected)
    }
    return collected,audit


def _read_price_csv(path, symbol):
    scripts_on_path()
    mod=import_numeric_script("07_get_prices.py","n2m_market_import")
    rows,kind=mod.parse_price_csv(path)
    return {r["date"]:float(r["close"]) for r in rows}, kind


NAS_PRICE_LINKS = {
    "NVDA": "https://www.nasdaq.com/market-activity/stocks/nvda/historical",
    "AAPL": "https://www.nasdaq.com/market-activity/stocks/aapl/historical",
    "GOOGL": "https://www.nasdaq.com/market-activity/stocks/googl/historical",
    "QQQ": "https://www.nasdaq.com/market-activity/etf/qqq/historical",
}


# The official dictionary is not redistributed. A local sibling copy can be
# reused after its content passes the same loader checks as a manually installed
# file. No network fetch or substitute word list is used.
LM_FILENAME = "Loughran-McDonald_MasterDictionary_1993-2025.csv"
LM_OFFICIAL_URL = "https://sraf.nd.edu/loughranmcdonald-master-dictionary/"


def lm_dictionary_status():
    destination=INPUTS / LM_FILENAME
    candidates=[ROOT.parent / name / "Inputs" / LM_FILENAME
                for name in ("News2Market", "News2Market_GitHub_Test")]
    if destination.is_file():
        return {"ready":True,"source":"this_project","file":f"Inputs/{LM_FILENAME}"}
    for path in candidates:
        if path.is_file():
            return {"ready":False,"available_to_reuse":True,"source":"existing_local_project",
                    "file":f"Inputs/{LM_FILENAME}"}
    return {"ready":False,"available_to_reuse":False,"source":"missing",
            "file":f"Inputs/{LM_FILENAME}","official_download":LM_OFFICIAL_URL}


def ensure_lm_dictionary(log=print):
    """Check official LM content before network news collection, copy a local
    validated sibling file if available. Never commit or download its contents.
    """
    scripts_on_path()
    from lm_dictionary import load_lm_dictionary
    destination=INPUTS / LM_FILENAME
    if not destination.is_file():
        for name in ("News2Market", "News2Market_GitHub_Test"):
            source=ROOT.parent / name / "Inputs" / LM_FILENAME
            if not source.is_file():
                continue
            try:
                source_lex=load_lm_dictionary(path=source)
                destination.parent.mkdir(parents=True,exist_ok=True)
                tmp=destination.parent / ("." + LM_FILENAME + ".tmp")
                try:
                    tmp.write_bytes(source.read_bytes())
                    if hashlib.sha256(tmp.read_bytes()).hexdigest()!=source_lex.sha256:
                        raise ValueError("Local dictionary integrity check failed")
                    os.replace(tmp,destination)
                finally:
                    tmp.unlink(missing_ok=True)
                log("Reused validated official LM dictionary from the existing local News2Market project")
                break
            except (OSError,ValueError) as exc:
                log(f"Skipped an invalid local dictionary candidate ({type(exc).__name__})")
    if not destination.is_file():
        raise RuntimeError(
            "Official Loughran–McDonald dictionary not installed. Before running research, "
            f"download {LM_FILENAME} from {LM_OFFICIAL_URL} and save it as Inputs/{LM_FILENAME}. "
            "If an earlier sibling News2Market project contains the official CSV, the dashboard can reuse it automatically. "
            "The full dictionary is not included in GitHub for redistribution-rights reasons. "
            "No news requests were started."
        )
    try:
        lex=load_lm_dictionary(path=destination)
    except (ValueError,OSError,UnicodeError) as exc:
        raise RuntimeError(
            f"Invalid official LM dictionary at Inputs/{LM_FILENAME}: {exc}. "
            f"Download a fresh copy from {LM_OFFICIAL_URL}. No news requests were started."
        ) from exc
    log(f"Official LM dictionary ready: {lex.file_words:,} terms; SHA-256 {lex.sha256[:12]}…")
    return lex


def _price_folder():
    folder=INPUTS / "prices"
    folder.mkdir(parents=True,exist_ok=True)
    return folder


def _nasdaq_manifest():
    path=_price_folder()/"SOURCE_MANIFEST.json"
    if not path.exists():return {}
    try:
        obj=json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else {}
    except (ValueError,OSError):return {}


def _nasdaq_evidence(symbol,path,manifest=None):
    """A verified original hash or explicit local Nasdaq import is required.

    A raw downloaded CSV has no ticker column, so source identity cannot be
    mathematically inferred from CSV content alone.
    """
    m=(manifest if manifest is not None else _nasdaq_manifest()).get(symbol,{})
    if not isinstance(m,dict):return False
    expected=str(m.get("sha256", ""))
    source=str(m.get("source", "")).lower()
    return ("nasdaq" in source and len(expected)==64 and
            hashlib.sha256(path.read_bytes()).hexdigest()==expected)


def validate_nasdaq_csv_text(text, symbol):
    """Validate manually downloaded Nasdaq Date + Close/Last CSV before saving."""
    if symbol not in NAS_PRICE_LINKS:
        raise ValueError("Unsupported symbol: choose NVDA, AAPL, GOOGL or QQQ")
    if not isinstance(text,str) or len(text.encode("utf-8")) > 2_000_000:
        raise ValueError("CSV must be UTF-8 text smaller than 2 MB")
    reader=csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    fields={re.sub(r"[^a-z0-9]", "",str(x).lower()):x for x in reader.fieldnames or []}
    if "date" not in fields or "closelast" not in fields:
        raise ValueError("Expected the Nasdaq daily-download columns: Date and Close/Last. Other vendors are not supported.")
    dates=set();prices={}
    for line_num,row in enumerate(reader,2):
        if not any(str(v or "").strip() for v in row.values()):continue
        rawdate=str(row[fields["date"]]).strip()
        try:
            from datetime import datetime as _datetime
            try:d=_datetime.strptime(rawdate,"%m/%d/%Y").date()
            except ValueError:d=_datetime.strptime(rawdate,"%Y-%m-%d").date()
            value=float(str(row[fields["closelast"]]).strip().replace("$", "").replace(",", ""))
            if not math.isfinite(value) or value<=0:raise ValueError("non-positive closing price")
        except (TypeError,ValueError) as exc:
            raise ValueError(f"Invalid Nasdaq price row {line_num}: {exc}") from exc
        ds=d.isoformat()
        if ds in dates:raise ValueError(f"Duplicate date {ds} in uploaded CSV")
        dates.add(ds);prices[ds]=value
    if len(prices)<3:raise ValueError("At least 3 valid daily prices are required")
    return {"symbol":symbol,"row_count":len(prices),"first_date":min(dates),"last_date":max(dates),
            "price_column":"Close/Last","cash_dividend_adjusted":False}


def import_nasdaq_csv(symbol,text,confirmed_nasdaq=False):
    """Save a user-confirmed file locally. No Nasdaq scraping or Yahoo calls."""
    if confirmed_nasdaq is not True:
        raise ValueError("Confirm that this CSV was obtained from Nasdaq's official historical data download")
    details=validate_nasdaq_csv_text(text,symbol)
    raw=text.encode("utf-8-sig") if not text.startswith("\ufeff") else text.encode("utf-8")
    folder=_price_folder(); dest=folder/f"{symbol}.csv"
    # Write only after validation; atomic replace protects existing local files.
    tmp=folder/f".{symbol}.csv.tmp"
    tmp.write_bytes(raw)
    os.replace(tmp,dest)
    sha=hashlib.sha256(raw).hexdigest()
    manifest=_nasdaq_manifest()
    manifest[symbol]={"source":"User-confirmed Nasdaq historical CSV import",
          "saved_as":f"{symbol}.csv","sha256":sha,"rows":details["row_count"],
          "first_date":details["first_date"],"last_date":details["last_date"],
          "price_semantics":"Raw Nasdaq Close/Last; cash dividends not adjusted",
          "dividend_adjusted":False,"nasdaq_page":NAS_PRICE_LINKS[symbol],
          "imported_utc":datetime.now(timezone.utc).isoformat(),
          "ticker_identity":"User confirmed ticker; Nasdaq CSV does not contain ticker identity"}
    manifest_path=folder/"SOURCE_MANIFEST.json"
    manifest_tmp=folder/".SOURCE_MANIFEST.tmp"
    manifest_tmp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    os.replace(manifest_tmp,manifest_path)
    return {**details,"sha256":sha,"saved_to":str(dest),"verified_nasdaq_provenance":"user_attested"}


def _reuse_previous_project_csv(symbol,log=print):
    """Reuse, never modify, an older sibling News2Market project's known Nasdaq file."""
    here=_price_folder()/f"{symbol}.csv"
    if here.exists():return here
    for old_name in ("News2Market", "News2Market_GitHub_Test"):
        candidate=ROOT.parent/old_name/"Inputs"/"prices"
        source=candidate/f"{symbol}.csv"
        if not source.is_file():continue
        manifest_path=candidate/"SOURCE_MANIFEST.json"
        try:
            old_manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            if not _nasdaq_evidence(symbol,source,old_manifest):
                log(f"Skipped unverified historical file: {source}")
                continue
            # Fully validated file, original project remains untouched.
            raw=source.read_bytes()
            tmp=here.with_name(f".{symbol}.csv.tmp")
            tmp.write_bytes(raw);os.replace(tmp,here)
            manifest=_nasdaq_manifest()
            manifest[symbol]={**old_manifest[symbol],"auto_reused_from":"sibling News2Market project"}
            mp=_price_folder()/"SOURCE_MANIFEST.json"
            mp.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            log(f"Reused verified Nasdaq {symbol}.csv from existing project ({old_manifest[symbol].get('rows')} days)")
            return here
        except (OSError,ValueError,KeyError,TypeError) as exc:
            log(f"Could not verify prior {symbol} CSV: {type(exc).__name__}")
    return here


def price_status(ticker):
    if ticker not in COMPANIES:raise ValueError("Unsupported company")
    pairs={}
    manifest=_nasdaq_manifest()
    for sym in (ticker,BENCHMARK):
        path=_price_folder()/f"{sym}.csv"
        is_verified=path.is_file() and _nasdaq_evidence(sym,path,manifest)
        entry={"symbol":sym,"ready":bool(is_verified),"local_file":f"Inputs/prices/{sym}.csv",
               "download_page":NAS_PRICE_LINKS[sym]}
        if is_verified:
            m=manifest[sym]
            entry.update({"rows":m.get("rows"),"first_date":m.get("first_date"),
                          "last_date":m.get("last_date"),"source":m.get("source")})
        pairs[sym]=entry
    return {"ticker":ticker,"benchmark":BENCHMARK,"files":pairs,
            "ready":all(x["ready"] for x in pairs.values()),
            "no_automatic_nasdaq_scraping":True}


def prices_for_pair(ticker,start,end,price_mode="auto",log=print):
    """Nasdaq-only, locally preserved CSV; never calls Yahoo or undocumented Nasdaq APIs."""
    if price_mode not in ("auto","nasdaq_csv","csv"):
        raise ValueError("Yahoo data is disabled; only user-downloaded Nasdaq CSVs are accepted")
    if price_mode=="auto":
        _reuse_previous_project_csv(ticker,log=log)
        _reuse_previous_project_csv(BENCHMARK,log=log)
    available=price_status(ticker)
    if not available["ready"]:
        missing=[s for s,x in available["files"].items() if not x["ready"]]
        raise RuntimeError("Missing verified Nasdaq historical CSV: "+", ".join(missing)+
            ". Use the 'Import Nasdaq CSV' section above to import official Date / Close/Last downloads. "
            "Nasdaq does not provide an authorized automated feed in this free research setup; no Yahoo fallback.")
    pa=_price_folder()/f"{ticker}.csv"
    pb=_price_folder()/f"{BENCHMARK}.csv"
    a,ka=_read_price_csv(pa,ticker)
    b,kb=_read_price_csv(pb,BENCHMARK)
    overlap=sorted(d for d in a.keys()&b.keys() if start.isoformat()<=d<=end.isoformat())
    if len(overlap)<3:raise RuntimeError("Fewer than 3 matching Nasdaq trading sessions in selected period")
    rows=[{"date":d,f"{ticker}_close":a[d],"QQQ_close":b[d],"source":"nasdaq_user_downloaded_csv"} for d in overlap]
    alerts=[]
    if (parse_day(overlap[0])-start).days > 10:
        alerts.append("The imported CSV begins later than the requested price window; download a longer Nasdaq date range for full coverage")
    if (end-parse_day(overlap[-1])).days > 7:
        alerts.append("The imported CSV ends before the requested price window; update both CSVs for recent sessions")
    audit={"provider":"nasdaq_local_csv","source":f"Nasdaq manually downloaded and locally verified CSVs: {pa.name}, {pb.name}",
           "price_basis":"Nasdaq Close/Last, split-methodology requires review; NOT cash-dividend adjusted",
           "ticker":ticker,"benchmark":BENCHMARK,"first_date":overlap[0],"last_date":overlap[-1],
           "matched_sessions":len(rows),"requested_start":start.isoformat(),"requested_end":end.isoformat(),
           "warnings":alerts,"no_synthetic_substitution":True,"no_yahoo":True,
           "sha256":{sym:hashlib.sha256((_price_folder()/f"{sym}.csv").read_bytes()).hexdigest()
                     for sym in (ticker,BENCHMARK)}}
    return rows,audit


def subprocess_stage(script,run_dir,ticker,date_start,date_end,log=print,env_extra=None,allow_error=False):
    if script not in SCRIPT_NAMES|{"12_local_llm_labels.py"}:
        raise ValueError("Unknown fixed stage")
    ctx={"ticker":ticker,"benchmark":BENCHMARK,"mode":"live", "source":"company_aware_news",
         "start_date":date_start,"end_date":date_end}
    context_path=run_dir/"context.json"
    write_json(context_path,ctx)
    env={**os.environ,"N2M_RESULTS_DIR":str(run_dir),"N2M_CONTEXT":str(context_path)}
    env.update(env_extra or {})
    log(f"Running {script}")
    completed=subprocess.run([sys.executable,str(SCRIPTS/script)],cwd=ROOT,env=env,
                             capture_output=True,text=True,timeout=500)
    tail=(completed.stdout+"\n"+completed.stderr).strip()[-3000:]
    (run_dir/("stage_"+script.replace(".py",".log"))).write_text(tail,encoding="utf-8")
    if completed.returncode and not allow_error:
        raise RuntimeError(f"{script} failed: {tail[-600:]}")
    return completed.returncode


def _interpret_prices_signals(run_dir,labels,prices,ticker,log=print):
    scripts_on_path()
    import signal_core
    import pandas as pd
    import statsmodels.api as sm
    import numpy as np
    out={"status":"not_estimated","reason":"No news signals aligned to later sessions", "signal_days":0,
         "regression":None,"correlation":None}
    try:
        daily,aligned,skipped=signal_core.construct(labels,prices,ticker,BENCHMARK)
    except (RuntimeError,ValueError,KeyError,TypeError) as e:
        out["reason"]=str(e)
        write_csv(run_dir/"08_daily_signals.csv",[],["signal_date","outcome_date","news_count","sentiment_score","next_excess_return"])
        return out,[]
    write_csv(run_dir/"08_daily_signals.csv",daily,list(daily[0]))
    out["signal_days"]=len(daily)
    out["article_mappings"]=len(aligned)
    out["skipped_articles"]=len(skipped)
    f=pd.DataFrame(daily)
    for name in ("sentiment_score","next_excess_return"):
        f[name]=pd.to_numeric(f[name],errors="coerce")
    f=f.dropna(subset=["sentiment_score","next_excess_return"])
    n=len(f)
    if n<8 or f["sentiment_score"].std()<1e-12:
        out["reason"]=f"Insufficient distinct signal days (n={n}; require >=8 and variable scores)"
        return out,daily
    x=f["sentiment_score"].to_numpy(float);y=f["next_excess_return"].to_numpy(float)
    model=sm.OLS(y,sm.add_constant(x)).fit(cov_type="HC1")
    out.update({"status":"exploratory_ols_only","reason":"No causal/predictive inference",
       "correlation":float(np.corrcoef(x,y)[0,1]) if np.std(y)>0 else None,
       "regression":{"beta":float(model.params[1]),"se_hc1":float(model.bse[1]),
                     "p_value":float(model.pvalues[1]),"r_squared":float(model.rsquared),
                     "n":n,"se_type":"HC1, NOT autocorrelation robust"}})
    log(f"Exploratory regression completed on {n} signal days (not predictive validation)")
    return out,daily


def _news_summary(run_dir,article_rows):
    score_rows=csv_rows(run_dir/"05_lm_labels.csv") if (run_dir/"05_lm_labels.csv").exists() else []
    clean_rows=csv_rows(run_dir/"11b_lm_original_vs_cleaned.csv") if (run_dir/"11b_lm_original_vs_cleaned.csv").exists() else []
    by_clean={r.get("article_id"):r for r in clean_rows}
    raw={r.get("article_id"):r for r in article_rows}
    rows=[]
    for s in score_rows:
        a=raw.get(s.get("article_id"),{})
        c=by_clean.get(s.get("article_id"),{})
        rows.append({"article_id":s["article_id"],"title":s["title"],
              "date":s["published_date"],"source":s["source"],"source_type":s["source_type"],
              "url":s["url"],"polarity":float(s["score"]) if s["score"] else None,
              "positive_per_1000":float(s.get("lm_positive_per_1000",0)),
              "negative_per_1000":float(s.get("lm_negative_per_1000",0)),
              "uncertainty_per_1000":float(s.get("lm_uncertainty_per_1000",0)),
              "polarity_hits":int(s.get("lm_polarity_hits",0)),
              "cleaned_polarity":float(c["lm_clean_score"]) if c.get("lm_clean_score") else None,
              "time_quality":a.get("published_time_quality","unknown")})
    write_csv(run_dir/"news_summary.csv",rows,["article_id","title","date","source","source_type","url",
       "polarity","positive_per_1000","negative_per_1000","uncertainty_per_1000",
       "polarity_hits","cleaned_polarity","time_quality"])
    return rows


def run_pipeline(options, log=print, news_loader=None, price_loader=None, root_output=None, now_day=None):
    """Single-company full pipeline. Injected loaders are ONLY for offline tests."""
    opt=validate_options(**options)
    scripts_on_path()
    ensure_lm_dictionary(log=log)  # Fail before market/news downloads.
    ticker=opt["ticker"]
    company=COMPANIES[ticker]
    today=now_day or datetime.now(timezone.utc).date()
    news_start=today-timedelta(days=opt["news_days"])
    price_start=subtract_years(today,opt["price_years"])
    runid=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base=(Path(root_output) if root_output is not None else RESULTS)/ticker/"Runs"
    run=base/runid
    run.mkdir(parents=True,exist_ok=False)
    report={"version":"News2Market_research_workbench","ticker":ticker,"company":company["name"],
       "benchmark":BENCHMARK,"status":"running","run_id":runid,"run_folder":str(run),
       "options":opt,"dates":{"news_start":news_start.isoformat(),"news_end":today.isoformat(),
       "prices_start":price_start.isoformat(),"prices_end":today.isoformat()},
       "limitations":["No market-price prediction, causal effect or trading backtest claim",
       "RSS/publisher timestamps do not verify first market-available instant",
       "Company relevance filtering is lexical and requires human review",
       "LM is a financial lexicon measure, not the signed surprise to investors",
       "Nasdaq CSVs are downloaded and imported by the user; automatic Nasdaq scraping is not enabled"],"warnings":[]}
    write_json(run/"research_report.json",report)
    try:
        log(f"Company: {ticker} — {company['name']}; benchmark: {BENCHMARK}")
        # Nasdaq-only market data first. Reuse verified local CSVs; never create synthetic data.
        price_fun=price_loader or prices_for_pair
        prices,price_audit=price_fun(ticker,price_start,today,opt["price_mode"],log=log)
        write_csv(run/"07_prices.csv",prices,["date",f"{ticker}_close","QQQ_close","source"])
        write_json(run/"07_price_audit.json",price_audit)
        report["prices"]={"audit":price_audit,"recent":prices[-50:]}
        log(f"Market data: {len(prices)} matched trading dates; {price_audit['provider']}")
        news_fun=news_loader or discover_news
        articles,news_audit=news_fun(company,ticker,news_start.isoformat(),today.isoformat(),
                                    opt["max_news"],use_proxy=opt["use_proxy"],log=log)
        # Both official & third party are preserved separately, never interpreted interchangeably.
        fields=["article_id","company","source","source_type","title","url","published_date",
                "published_time_quality","text","text_chars","retrieved_utc","synthetic",
                "extraction_strategy","extraction_paragraphs"]
        cleaned=[];seen=set()
        for a in articles:
            if a.get("synthetic") in (True,"True","true",1):continue
            if a.get("company") not in (company["name"],ticker,*( ["NVIDIA CORPORATION"] if ticker=="NVDA" else [])):
                report["warnings"].append("Article company mismatch excluded");continue
            url=a.get("url","")
            parsed=urlparse(url)
            if parsed.scheme!="https" or not parsed.hostname or not a.get("text") or len(a["text"])<100:continue
            if a.get("published_date","")<news_start.isoformat() or a.get("published_date","")>today.isoformat():continue
            key=(url.rstrip("/").casefold(),a.get("title",""))
            if key in seen:continue
            seen.add(key)
            a["company"]=company["name"]
            cleaned.append(a)
            if len(cleaned)>=opt["max_news"]:break
        write_csv(run/"04_articles.csv",cleaned,fields)
        write_json(run/"news_audit.json",news_audit)
        report["news"]={"count":len(cleaned),"audit":news_audit}
        log(f"Qualified article bodies: {len(cleaned)}")
        if cleaned:
            for name in ["05_lm_sentiment.py","11_prepare_text.py","11b_lm_cleaned.py","06_event_tags.py"]:
                subprocess_stage(name,run,ticker,news_start.isoformat(),today.isoformat(),log=log)
            news_rows=_news_summary(run,cleaned)
            report["news"]["articles"]=news_rows
            labels=csv_rows(run/"06_labels_with_events.csv")
            returns,daily=_interpret_prices_signals(run,labels,prices,ticker,log=log)
            report["returns"]=returns
            report["daily_signals"]=daily
            if opt["local_llm"]:
                log("Running optional Qwen2.5:1.5b on at most 5 news articles")
                try:
                    code=subprocess_stage("12_local_llm_labels.py",run,ticker,news_start.isoformat(),today.isoformat(),
                        log=log,allow_error=True,env_extra={"N2M_LLM_MODEL":MODEL,
                            "N2M_LLM_MAX_CHARS":"1000","N2M_LLM_CONTEXT":"2048",
                            "N2M_LLM_MAX_ARTICLES":str(min(5,len(cleaned)))})
                    report["llm"]={"status":"audit_outputs_written" if code==0 else "failed_validation_or_runtime",
                        "model":MODEL,"no_human_ground_truth":True}
                except Exception as exc:
                    report["llm"]={"status":"failed","message":str(exc)[:300],"model":MODEL}
            else:
                report["llm"]={"status":"off_by_default","model":MODEL}
        else:
            report["news"]["articles"]=[]
            report["returns"]={"status":"not_estimated","reason":"No publisher full-text articles returned", "signal_days":0}
            report["daily_signals"]=[]
            report["llm"]={"status":"not_run_no_text"}
            report["warnings"].append("No eligible news bodies: market prices remain available; no artificial scores/regression")
        report["status"]="complete_with_warnings" if report["warnings"] else "complete"
    except Exception as exc:
        report["status"]="failed"
        report["error"]=f"{type(exc).__name__}: {str(exc)[:550]}"
        write_json(run/"research_report.json",report)
        raise RuntimeError(f"{report['error']} | partial run preserved: {run}") from exc
    write_json(run/"research_report.json",report)
    log(f"COMPLETE: {run}")
    return report
