"""Loughran-McDonald research dictionary counts, no paid services."""
from __future__ import annotations
from common import RESULTS, config,read_csv,write_csv,json_dump,message
from lm_dictionary import load_lm_dictionary,LM_SOURCE,LM_VERSION

def label_articles(articles,lex,char_cap):
    rows=[]
    for article in articles:
        m=lex.score(article.get('title',''),article.get('text',''),char_cap)
        no=m['lm_no_polarity_hits']
        rows.append({**{k:article.get(k,'') for k in ('article_id','title','source','source_type','url','published_date','published_time_quality','synthetic')},
                     **m,'score':'' if no else m['score'],
                     'sentiment':'unscorable_no_polarity_hits' if no else m['sentiment'],
                     'event_type':'Other','label_method':'lm','label_status':'lm_no_polarity_hits' if no else 'lm_financial_dictionary'})
    return rows

def main():
    cfg=config();articles=read_csv(RESULTS/'04_articles.csv')
    lex=load_lm_dictionary()
    rows=label_articles(articles,lex,cfg['labeling']['lm_text_chars'])
    write_csv(RESULTS/'05_lm_labels.csv',rows)
    json_dump(RESULTS/'05_lm_audit.json',{'lexicon_source':LM_SOURCE,'lexicon_version':LM_VERSION,
         'sha256':lex.sha256,'terms':lex.file_words,'article_count':len(rows),
         'polarity_hit_articles':sum(not r['lm_no_polarity_hits'] for r in rows),
         'no_polarity_hit_articles':sum(r['lm_no_polarity_hits'] for r in rows),
         'score_formula':'(positive-negative)/(positive+negative), missing if both zero',
         'tokenizer':'A-Za-z words 2+ chars, full-word exact matches, no stemming',
         'note':'LM developed for financial disclosures; external validity in news/press releases requires audit.'})
    message(f"Official LM dictionary: {len(rows)} texts; {sum(not r['lm_no_polarity_hits'] for r in rows)} have polarity hits; SHA256={lex.sha256[:12]}...")

if __name__=='__main__': main()
