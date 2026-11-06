"""Date-only releases -> next session close, outcome following close-to-close return."""
from __future__ import annotations
import bisect
import pandas as pd
from common import RESULTS, config, read_csv, write_csv, message, json_dump


def construct(labels, price_rows, ticker='NVDA', benchmark='QQQ'):
    p=pd.DataFrame(price_rows).copy()
    p['date']=pd.to_datetime(p['date']).dt.normalize()
    p=p.sort_values('date').drop_duplicates('date')
    p[f'{ticker}_close']=pd.to_numeric(p[f'{ticker}_close'],errors='coerce')
    p[f'{benchmark}_close']=pd.to_numeric(p[f'{benchmark}_close'],errors='coerce')
    p=p.dropna(subset=[f'{ticker}_close',f'{benchmark}_close'])
    p=p[(p[f'{ticker}_close']>0)&(p[f'{benchmark}_close']>0)]
    p['r_asset']=p[f'{ticker}_close'].pct_change()
    p['r_benchmark']=p[f'{benchmark}_close'].pct_change()
    p['next_excess_return']=(p['r_asset']-p['r_benchmark']).shift(-1)
    sessions=list(p['date'])
    if not sessions:
        raise RuntimeError('No valid price sessions')
    signals=[]
    failed=[]
    for row in labels:
        if not str(row['score']).strip():
            continue
        pub=pd.Timestamp(row['published_date']).normalize()
        # DATE ONLY => cannot know article available at close on publication day.
        # To avoid using stale/current-day intraday returns, use first later close
        # as signal decision time; predict next full session close-to-close.
        idx=bisect.bisect_right(sessions,pub)
        if idx>=len(sessions)-1:
            failed.append({'article_id':row['article_id'],'reason':'no_future_price_day'})
            continue
        if idx<0:
            failed.append({'article_id':row['article_id'],'reason':'invalid_date'})
            continue
        signal_day=sessions[idx]
        signals.append({'article_id':row['article_id'], 'published_date':row['published_date'],
                        'signal_date':signal_day.date().isoformat(),
                        'score':float(row['score']), 'event_type':row['event_type'],
                        'source':row['source'], 'label_method':row['label_method'],
                        **({field:float(row[field]) for field in (
                            'lm_positive_per_1000','lm_negative_per_1000','lm_uncertainty_per_1000')
                            if row.get(field,'') not in ('',None)} if row['label_method']=='lm' else {})})
    df=pd.DataFrame(signals)
    if df.empty:
        raise RuntimeError('No labels could be aligned with future trading sessions')
    daily=df.groupby('signal_date',as_index=False).agg(
        sentiment_score=('score','mean'),news_count=('score','size'))
    # LM rates are per 1,000 words in each article; equal-weight daily mean across articles.
    if 'lm_positive_per_1000' in df.columns:
        lm_daily=df.groupby('signal_date',as_index=False).agg(
            lm_positive_per_1000=('lm_positive_per_1000','mean'),
            lm_negative_per_1000=('lm_negative_per_1000','mean'),
            lm_uncertainty_per_1000=('lm_uncertainty_per_1000','mean'))
        daily=daily.merge(lm_daily,on='signal_date',how='left')
    daily['date']=pd.to_datetime(daily['signal_date'])
    daily=daily.merge(p[['date','next_excess_return']],on='date',how='left')
    daily['outcome_date']=daily['date'].map(dict(zip(p['date'],p['date'].shift(-1)))).dt.strftime('%Y-%m-%d')
    daily=daily.dropna(subset=['next_excess_return','outcome_date'])
    if daily.empty:
        raise RuntimeError('No valid next-session returns aligned to signal dates')
    daily['signal_date']=daily['date'].dt.strftime('%Y-%m-%d')
    daily['next_excess_return']=daily['next_excess_return'].astype(float)
    cols=['signal_date','outcome_date','news_count','sentiment_score','next_excess_return']
    cols += [name for name in ('lm_positive_per_1000','lm_negative_per_1000','lm_uncertainty_per_1000') if name in daily.columns]
    result=daily[cols].to_dict('records')
    return result, signals, failed


def main():
    cfg=config()
    labels=read_csv(RESULTS/'02_article_labels.csv')
    prices=read_csv(RESULTS/'03_prices.csv')
    daily,articles,skipped=construct(labels,prices,cfg['project']['ticker'],cfg['project']['benchmark'])
    write_csv(RESULTS/'04_daily_signals.csv',daily)
    write_csv(RESULTS/'04_article_time_alignment.csv',articles)
    json_dump(RESULTS/'04_time_alignment_audit.json',{
        'article_mappings':len(articles),'mapped_signal_days':len(daily),
        'skipped':skipped, 'rule': 'publication date only -> first later trading-date CLOSE -> following CLOSE-to-CLOSE excess return',
        'limitation':'Ignores potentially measurable release time; conservative timing convention does not prove exogeneity.'})
    message(f'Constructed {len(daily)} daily signal observations from {len(articles)} article mappings.')

if __name__=='__main__':
    main()
