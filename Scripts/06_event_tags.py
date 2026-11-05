"""FREE rule-based tentative event tags, NOT an LLM and NOT validated economic channels."""
from __future__ import annotations
import re
from common import RESULTS,read_csv,write_csv,json_dump,message

EVENTS={
 'AI demand':['demand','adoption','customer','data center','ai infrastructure'],
 'Technological innovation':['innovation','new platform','launch','new generation','architecture'],
 'Capital expenditure':['capital expenditure','capex','capital spending','investment'],
 'Regulation':['regulation','license','export control','restriction','sanctions'],
 'Earnings':['earnings','revenue','net income','gross margin','guidance'],
 'Supply constraints':['shortage','bottleneck','supply chain','capacity','shipment'],
 'Competition':['competitor','competing','market share','rival'],
 'Firm fundamentals':['profit','cost of sales','cash flow','operating expense'],
}

def tag_event(title,body):
    text=(title+' '+(body or '')[:3000]).lower()
    hits={event:sum(len(re.findall(r'(?<![a-z])'+re.escape(term)+r'(?![a-z])',text)) for term in terms) for event,terms in EVENTS.items()}
    winner=max(hits,key=hits.get)
    return (winner if hits[winner]>0 else 'Other'),hits

def main():
    labels=read_csv(RESULTS/'05_lm_labels.csv')
    articles={x['article_id']:x for x in read_csv(RESULTS/'04_articles.csv')}
    for row in labels:
        a=articles[row['article_id']]
        event,hits=tag_event(a['title'],a['text'])
        row['event_type']=event
        row['event_method']='UNVALIDATED_RULE_BASED'
        row['event_hits']=str(hits)
    write_csv(RESULTS/'06_labels_with_events.csv',labels)
    json_dump(RESULTS/'06_event_audit.json',{'method':'heuristic word-based event tagging, not GPT or a trained model',
       'warning':'Do not interpret these categories as verified economic mechanisms. Human labeling required.'})
    message(f'Free rule-based event categories assigned to {len(labels)} texts (not independently validated).')

if __name__=='__main__': main()
