"""Sensitivity comparison: official LM dictionary on cleaned narrative vs original full text."""
from __future__ import annotations
from scripts.shared.common import RESULTS,config,read_csv,write_csv,json_dump,message
from scripts.step_03_nlp.lm_dictionary import load_lm_dictionary

FIELDS=['article_id','title','source_type','published_date','raw_chars','narrative_chars',
        'lm_raw_score','lm_clean_score','lm_clean_positive','lm_clean_negative',
        'lm_clean_uncertainty','lm_clean_unscorable','cleaning_rule']

def compare(rows,raw_scores,lex):
    lookup={x['article_id']:x for x in raw_scores}
    out=[]
    for r in rows:
        m=lex.score(r.get('title',''),r.get('narrative_text',''),30000)
        raw=lookup.get(r['article_id'],{})
        out.append({'article_id':r['article_id'],'title':r.get('title',''),'source_type':r.get('source_type',''),
           'published_date':r.get('published_date',''),'raw_chars':r['raw_text_chars'],'narrative_chars':r['narrative_chars'],
           'lm_raw_score':raw.get('score',''),'lm_clean_score':'' if m['lm_no_polarity_hits'] else m['score'],
           'lm_clean_positive':m['lm_positive_count'],'lm_clean_negative':m['lm_negative_count'],
           'lm_clean_uncertainty':m['lm_uncertainty_count'],'lm_clean_unscorable':m['lm_no_polarity_hits'],
           'cleaning_rule':r['boilerplate_rule']})
    return out

def main():
    rows=read_csv(RESULTS/'11_nlp_ready_articles.csv')
    raw=read_csv(RESULTS/'05_lm_labels.csv')
    lex=load_lm_dictionary()
    out=compare(rows,raw,lex)
    write_csv(RESULTS/'11b_lm_original_vs_cleaned.csv',out,FIELDS)
    json_dump(RESULTS/'11b_audit.json',{'count':len(out),'comparison':'Same official dictionary; only body treatment differs.',
       'warning':'Headline included in both scores, LLM and LM still measure different constructs. Earlier regression uses raw LM scores.'})
    message(f'LM raw vs cleaned narrative computed: {len(out)} comparisons.')

if __name__=='__main__':main()
