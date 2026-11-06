"""Time-ordered, held-out human-label comparison; no financial-alpha claims."""
from __future__ import annotations
import csv
from collections import Counter
from datetime import date
from pathlib import Path

ALLOWED_LABELS={"negative","neutral","positive"}
ALLOWED_SOURCES={"human_verified","independent_manual"}


class EvaluationNotSupported(ValueError):
    pass


def read_human_labels(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    needed={"article_id","label","label_source"}
    if not rows or not needed.issubset(rows[0]):
        raise EvaluationNotSupported("Use an independent labels CSV with article_id,label,label_source columns")
    result={}
    for r in rows:
        k=r['article_id'].strip();label=r['label'].strip().lower()
        if r['label_source'].strip().lower() not in ALLOWED_SOURCES:
            raise EvaluationNotSupported("AI-assisted/self-generated reference labels cannot be used as independent ground truth")
        if not k or label not in ALLOWED_LABELS or k in result:
            raise EvaluationNotSupported("Invalid, blank, or duplicate independent human label")
        result[k]=label
    return result


def chrono_split(rows,labels, min_docs=30):
    data=[];hashes=set()
    for r in rows:
        aid=str(r.get('article_id',''))
        if aid not in labels:continue
        try:d=date.fromisoformat(str(r.get('published_date',''))[:10])
        except ValueError:continue
        text=(str(r.get('title') or '')+' '+str(r.get('text') or '')).strip()
        if len(text)<25:continue
        data.append((d,aid,text,labels[aid]))
    data.sort(key=lambda r:(r[0],r[1]))
    if len(data)<min_docs or len(set(x[0] for x in data))<8:
        raise EvaluationNotSupported(f"Need >={min_docs} independently labeled texts on >=8 dates (found {len(data)})")
    dates=sorted(set(x[0] for x in data));cut=dates[max(1,int(len(dates)*0.7))-1]
    train=[r for r in data if r[0]<=cut];test=[r for r in data if r[0]>cut]
    if len(train)<15 or len(test)<8:
        raise EvaluationNotSupported("Chronological split does not contain enough training/test articles")
    for section,items in (("train",train),("test",test)):
        if len({x[3] for x in items})<2:
            raise EvaluationNotSupported(f"{section} split requires at least two sentiment classes")
    from hashlib import sha256
    h_train={sha256(x[2].lower().encode()).hexdigest() for x in train}
    h_test={sha256(x[2].lower().encode()).hexdigest() for x in test}
    if h_train.intersection(h_test):
        raise EvaluationNotSupported("Exact duplicate text appears in both train and holdout; deduplicate first")
    return train,test


def benchmark_human_labels(rows,labels,lex):
    """Compare LM rule vs supervised TF-IDF on SAME holdout; train-only vectorizer fit."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score,balanced_accuracy_score,accuracy_score
    train,test=chrono_split(rows,labels)
    v=TfidfVectorizer(stop_words='english',ngram_range=(1,2),max_features=5000, min_df=1)
    xtrain=v.fit_transform([r[2] for r in train]); xtest=v.transform([r[2] for r in test])
    model=LogisticRegression(max_iter=1000,random_state=42,class_weight='balanced')
    model.fit(xtrain,[r[3] for r in train])
    truth=[r[3] for r in test]
    pred=[str(x) for x in model.predict(xtest)]
    def score(predictions,y):
        return {'n':len(y),'macro_f1':round(float(f1_score(y,predictions,average='macro',zero_division=0)),5),
          'balanced_accuracy':round(float(balanced_accuracy_score(y,predictions)),5),
          'accuracy':round(float(accuracy_score(y,predictions)),5)}
    lmtruth=[];lmpred=[];tfidfcovered=[]
    for r,pr in zip(test,pred):
        m=lex.score('',r[2],char_cap=200_000)
        if m['lm_no_polarity_hits']:
            continue
        pol=m['score']
        label='positive' if pol>0.15 else ('negative' if pol<-.15 else 'neutral')
        lmtruth.append(r[3]);lmpred.append(label);tfidfcovered.append(pr)
    result={"status":"held_out_temporal_experiment_not_market_validation",
        "train_count":len(train),"test_count":len(test),
        "train_last_date":max(r[0] for r in train).isoformat(),
        "test_first_date":min(r[0] for r in test).isoformat(),
        "labels":"user_asserted_independent_human_verified_not_audited_by_code",
        "tfidf_logistic_all_holdout":score(pred,truth),
        "lm_coverage_on_holdout":round(len(lmtruth)/len(test),4),
        "lm_on_covered_holdout":score(lmpred,lmtruth) if lmtruth else None,
        "tfidf_on_lm_covered_holdout":score(tfidfcovered,lmtruth) if lmtruth else None,
        "methods":{"lm":"thresholded (P-N)/(P+N) with heuristic ±0.15, missing excluded",
                   "tfidf":"training-only fitted unigram/bigram TF-IDF + class-weighted logistic regression"},
        "caveat":"No pretrained transformer or XLex implementation is claimed; labels must be independently validated, and results are not stock-return forecasts"}
    return result
