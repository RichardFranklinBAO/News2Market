"""Date-only public information -> first later session close -> following session return."""
from __future__ import annotations
from common import RESULTS,config,read_csv,write_csv,json_dump,message
from signal_core import construct

def main():
    cfg=config();ticker=cfg['project']['ticker'];benchmark=cfg['project']['benchmark']
    labels=read_csv(RESULTS/'06_labels_with_events.csv')
    prices=read_csv(RESULTS/'07_prices.csv')
    rows,matched,skipped=construct(labels,prices,ticker,benchmark)
    write_csv(RESULTS/'08_daily_signals.csv',rows)
    write_csv(RESULTS/'08_article_alignment.csv',matched)
    json_dump(RESULTS/'08_alignment_audit.json',{
      'signal_dates':len(rows),'article_mappings':len(matched),'skipped':skipped,
      'rule':'Only dated releases: first market close AFTER reported date becomes decision time, outcome is following close-to-close asset-minus-benchmark return',
      'warning':'Conservative date-only mapping avoids same-day lookahead, but does NOT prove release time, causal identification or predictability.'})
    message(f'Built {len(rows)} trade-date signal rows from {len(matched)} article mappings.')

if __name__=='__main__': main()
