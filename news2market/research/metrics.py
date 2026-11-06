"""Transparent research-only text features and optional TF-IDF diagnostics.

TF-IDF is an unsupervised representation, not an economic sentiment measure.
XLex is not claimed to be implemented or reproduced by this file.
"""
from __future__ import annotations
from collections import Counter
import csv
import hashlib
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]


def load_official_lm(dictionary_path: str | Path):
    scripts=ROOT/"Scripts"
    if not (scripts/"lm_dictionary.py").is_file():
        raise FileNotFoundError("Existing News2Market Scripts/lm_dictionary.py not available")
    if str(scripts) not in sys.path:
        sys.path.insert(0,str(scripts))
    from lm_dictionary import load_lm_dictionary
    return load_lm_dictionary(Path(dictionary_path))


def canonical_rows(rows):
    """Preserve source provenance and remove exact duplicated article IDs/URLs."""
    accepted=[];seen_ids=set();seen_urls=set();excluded=[]
    for i,original in enumerate(rows):
        row=dict(original)
        article_id=str(row.get("article_id") or f"row-{i}").strip()
        url=str(row.get("url") or "").strip()
        if article_id in seen_ids or (url and url.lower().rstrip("/") in seen_urls):
            excluded.append({"article_id":article_id,"reason":"duplicate_article_id_or_url"});continue
        seen_ids.add(article_id)
        if url: seen_urls.add(url.lower().rstrip("/"))
        row["article_id"]=article_id
        row["text"]=(row.get("text") or row.get("body") or row.get("full_text") or "")
        row["published_date"]=(row.get("published_date") or row.get("filingDate") or "")
        accepted.append(row)
    return accepted,excluded


def measure_rows(rows,lex, char_cap=200_000):
    features=[]; no_text=0; missing_polarity=0
    for r in rows:
        body=str(r.get("text") or "")
        title=str(r.get("title") or "")
        if len(body.strip())<30:
            no_text+=1
        m=lex.score(title,body,char_cap=char_cap)
        if m["lm_no_polarity_hits"]:missing_polarity+=1
        features.append({
          "article_id":r.get("article_id",""), "ticker":r.get("ticker",""),
          "published_date":r.get("published_date",""),"accepted_datetime_raw":r.get("accepted_datetime_raw",""),
          "published_time_quality":r.get("published_time_quality",""),
          "source":r.get("source",""),"source_type":r.get("source_type",""),"form":r.get("form",""),
          "url":r.get("url",""),"title":title,"text_status":r.get("text_status",""),
          "text_sha256":hashlib.sha256(body.encode('utf-8')).hexdigest() if body else "",
          "text_chars":len(body),"lm_positive_count":m["lm_positive_count"],
          "lm_negative_count":m["lm_negative_count"],
          "lm_uncertainty_count":m["lm_uncertainty_count"],
          "lm_positive_per_1000":m["lm_positive_per_1000"],
          "lm_negative_per_1000":m["lm_negative_per_1000"],
          "lm_uncertainty_per_1000":m["lm_uncertainty_per_1000"],
          "lm_polarity": "" if m["lm_no_polarity_hits"] else m["score"],
          "lm_polarity_hits":m["lm_polarity_hits"],
          "lm_token_count":m["lm_token_count"],"lm_text_truncated":m["lm_text_truncated"],
        })
    return features,{"documents":len(features),"short_or_missing_bodies":no_text,
                     "missing_lm_polarity":missing_polarity,"dictionary_sha256":lex.sha256,
                     "lm_measurement_definition":"word counts per 1,000 dictionary-tokenized words; secondary (P-N)/(P+N) if P+N>0"}


def tfidf_descriptives(rows, max_features=2500, top_k=8):
    """Descriptive vocabulary features fitted on this corpus; NOT an OOS model."""
    data=[(str(r.get("title") or "")+" "+str(r.get("text") or "")).strip() for r in rows]
    if sum(bool(x) for x in data)<2:
        return [],{"status":"insufficient_texts","tfidf_is_sentiment":False}
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        return [],{"status":"sklearn_not_installed","tfidf_is_sentiment":False}
    vectorizer=TfidfVectorizer(stop_words="english",ngram_range=(1,2),min_df=1,max_features=max_features,
                               token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b")
    try:
        matrix=vectorizer.fit_transform(data)
    except ValueError:
        return [],{"status":"empty_vocabulary","tfidf_is_sentiment":False}
    terms=vectorizer.get_feature_names_out()
    output=[]
    for i,row in enumerate(rows):
        dense=matrix.getrow(i)
        order=sorted(zip(dense.indices,dense.data),key=lambda x:-x[1])[:top_k]
        for j,w in order:
            output.append({"article_id":row.get("article_id",""),"term":str(terms[j]),"tfidf_weight":round(float(w),6)})
    return output,{"status":"descriptive_only_not_sentiment", "vocabulary_size":len(terms),
                   "documents":len(rows),"top_terms_per_document":top_k,"tfidf_is_sentiment":False,
                   "warning":"Vectorizer fitted on full corpus for descriptive analysis only; refit on training data for predictive evaluation"}


def read_articles_csv(path):
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(str(p))
    if p.stat().st_size > 50_000_000:raise ValueError("CSV exceeds 50 MB local research cap")
    with p.open(encoding="utf-8-sig",newline="") as f:
        data=list(csv.DictReader(f))
    if not data:raise ValueError("CSV contains no article rows")
    if not any(k in data[0] for k in ("text","body","full_text")):
        raise ValueError("CSV requires text, body, or full_text column")
    return data


def write_rows(path, rows, fields=None):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
