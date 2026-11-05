"""Exploratory OLS diagnostics; 100% offline, no paid APIs."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import statsmodels.api as sm
from common import RESULTS,config,read_csv,write_csv,json_dump,message

def analyze(rows,min_days=8):
    df=pd.DataFrame(rows)
    for c in ('sentiment_score','next_excess_return','news_count'):
        df[c]=pd.to_numeric(df[c],errors='coerce')
    df=df.dropna(subset=['sentiment_score','next_excess_return'])
    x=df.sentiment_score.to_numpy(dtype=float)
    y=df.next_excess_return.to_numpy(dtype=float)
    n=len(df)
    corr=float(np.corrcoef(x,y)[0,1]) if n>=3 and np.std(x)>0 and np.std(y)>0 else None
    regression=None
    if n>=min_days and np.std(x)>1e-9:
        mdl=sm.OLS(y,sm.add_constant(x)).fit(cov_type='HC1')
        ci=mdl.conf_int()
        regression={'intercept':float(mdl.params[0]),'beta_sentiment':float(mdl.params[1]),
          'se_hc1':float(mdl.bse[1]),'p_value_exploratory':float(mdl.pvalues[1]),
          'r_squared':float(mdl.rsquared),'ci_95_hc1':ci[1].tolist(),'n':n,
          'se_type':'HC1; not autocorrelation-robust; pilot only'}
    return df,corr,regression

def main():
    cfg=config();ctx=cfg['_context'];ticker=cfg['project']['ticker'];benchmark=cfg['project']['benchmark']
    rows=read_csv(RESULTS/'08_daily_signals.csv')
    labels=read_csv(RESULTS/'06_labels_with_events.csv')
    articles=read_csv(RESULTS/'04_articles.csv')
    df,corr,reg=analyze(rows,cfg['analysis']['min_regression_days'])
    synthetic=ctx['mode']=='demo'
    if not synthetic and any(str(a.get('synthetic','')).strip().lower()=='true' for a in articles):
        raise RuntimeError('Live run contains synthetic articles; refusing to present as empirical evidence.')
    price_audit=json.loads((RESULTS/'07_price_audit.json').read_text(encoding='utf-8'))
    lm_audit=json.loads((RESULTS/'05_lm_audit.json').read_text(encoding='utf-8'))
    n=len(df)
    summary={'status':'DEMO - NO REAL EVIDENCE' if synthetic else 'LIVE PILOT - EXPLORATORY',
      'ticker':ticker,'benchmark':benchmark,'source':ctx['source'],
      'article_count':len(articles),'valid_polarity_article_count':sum(bool(str(a.get('score','')).strip()) for a in labels),
      'signal_days':n,'pearson_correlation':corr,'regression':reg,
      'lm_sha256':lm_audit['sha256'],'lm_source':lm_audit['lexicon_source'],
      'price_data_provenance':price_audit,
      'cautions':[
         'No causal interpretation or forecast performance claim; no holdout / robust risk adjustment.',
         'Information dates have no verified intraday timestamps; first-later-close convention used.',
         'Firm filings and press releases are NOT independent news; source selection differs by ticker.',
         'LM financial tone counts are NOT economic expectations, not causal mechanisms, and may be sparse.',
         'Event labels are UNVALIDATED heuristic keyword matches, not an LLM.',
         'QQQ return difference is not a risk-factor-adjusted abnormal return.',
         'Local CSV price adjustment status and historical corporate actions require review.',
         'Small samples can produce unstable HC1 standard errors.']}
    json_dump(RESULTS/'09_analysis_summary.json',summary)
    if n:
        x=df.sentiment_score.to_numpy(dtype=float);y=df.next_excess_return.to_numpy(dtype=float)
        fig,ax=plt.subplots(figsize=(7.5,4.6))
        ax.scatter(x,y,alpha=.65)
        ax.axhline(0,linestyle='--',color='gray',linewidth=1)
        if reg:
            xx=np.linspace(min(x),max(x),100)
            ax.plot(xx,reg['intercept']+reg['beta_sentiment']*xx)
        ax.set_xlabel('Daily LM polarity score (positive-negative)/(positive+negative)')
        ax.set_ylabel(f'Next-session {ticker} return minus {benchmark} return')
        ax.set_title('SYNTHETIC DEMO — NOT MARKET EVIDENCE' if synthetic else f'{ticker} exploratory public-text measurement')
        fig.tight_layout();fig.savefig(RESULTS/'09_signal_vs_return.png',dpi=160);plt.close(fig)
    else:
        message('No valid daily signal rows to plot; see data and alignment audit.')
    write_csv(RESULTS/'09_human_audit_template.csv',[{'article_id':x['article_id'],'title':x['title'],
      'lm_sentiment':x['sentiment'],'rule_event':x['event_type'],
      'human_sentiment':'','human_event':'','body_quality_check':'','notes':''} for x in labels[:min(15,len(labels))]])
    (RESULTS/'09_research_notes.md').write_text('\n'.join([
      f'# News2Market — {ticker}',f'Mode: {summary["status"]}',f'Articles: {len(articles)}',
      f'Usable signal days: {n}',f'Pearson correlation: {corr}',
      'Regression: '+(json.dumps(reg,indent=2) if reg else 'Not estimated: too few distinct signal dates or constant scores.'),
      '\n## Cautions',*['- '+x for x in summary['cautions']]])+'\n',encoding='utf-8')
    message(f'Validation: {n} signal days, regression {"estimated" if reg else "NOT estimated"}, synthetic={synthetic}.')

if __name__=='__main__': main()
