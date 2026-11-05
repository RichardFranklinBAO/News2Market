"""Reproducible, explicitly SYNTHETIC sample for code-only smoke tests."""
from __future__ import annotations
import hashlib
from datetime import datetime
import numpy as np
import pandas as pd
from common import INPUTS, config, write_csv, message

DEMO_EVENTS = [
  ('AI infrastructure demand expands','AI demand','New customer orders accelerate growth in demand for AI accelerator capacity.'),
  ('New export restrictions create policy uncertainty','Regulation','New rules may limit shipments and raise compliance costs for the company.'),
  ('Strategic partnership adds cloud GPU deployments','AI demand','A cloud partner announces new accelerator deployments and expanded infrastructure investment.'),
  ('Manufacturing bottleneck affects delivery schedules','Supply constraints','Packaging capacity shortage delays delivery of high-demand AI systems.'),
  ('Quarterly outlook highlights revenue growth','Earnings','Updated quarterly earnings outlook indicates strong revenue growth and customer orders.'),
  ('Rival announces competing accelerator platform','Competition','A competitor unveils a new AI chip that may challenge incumbent market share.'),
  ('New data center product becomes available','Technological innovation','The next-generation platform is launched and improves performance per watt.'),
  ('Supply agreement improves component availability','Supply constraints','New manufacturing supply agreement eases prior production bottleneck.'),
  ('Increased operating costs weigh on margins','Firm fundamentals','The firm reports higher operating costs and lower margin outlook.'),
  ('Major capital expenditure program announced','Capital expenditure','The company plans additional investment in testing and research infrastructure.'),
  ('Customer contract for accelerated computing','AI demand','A major new customer contract supports future demand and expected revenue.'),
  ('Potential legal inquiry on market access','Regulation','A possible regulatory investigation adds uncertainty and downside risks.'),
  ('Expansion of enterprise AI software ecosystem','Technological innovation','New enterprise platform brings broader adoption with partners.'),
  ('Competitor faces product delays','Competition','A rival faces shipment delays, creating potential demand upside for NVIDIA.'),
  ('Weakening enterprise order book','AI demand','Channel checks suggest lower orders and weaker AI spending for next quarter.'),
  ('Optimistic guidance on next fiscal period','Earnings','Management increases guidance after stronger than expected results.'),
  ('Data center infrastructure capacity grows','Capital expenditure','A collaboration expands data center capacity to serve new enterprise clients.'),
  ('New export licensing delays','Regulation','Additional export license requirements delay overseas orders.'),
  ('Memory supply disruption','Supply constraints','A component shortage limits shipments and increases supply costs.'),
  ('Lower-cost accelerator design released','Technological innovation','New product design lowers cost and improves energy efficiency.'),
  ('Lower gross-margin guidance','Earnings','Management reports lower gross margin guidance due to product mix.'),
  ('Strong developer adoption','AI demand','Developer adoption and expanding usage support future long-run demand.'),
  ('Major research investment announced','Capital expenditure','Planned research spending may increase near-term operating costs.'),
  ('Industry policy outlook stabilizes','Regulation','Authorities provide clearer rules and reduce uncertainty about upcoming restrictions.'),
]

def main():
    cfg = config()
    dates = pd.bdate_range('2026-08-04', '2026-10-30', periods=None)
    # Every 2-3 business sessions, 24 different publication dates. No real observations.
    indices = np.linspace(0, len(dates)-5, len(DEMO_EVENTS), dtype=int)
    rows=[]
    for i, (title, category, summary) in enumerate(DEMO_EVENTS):
        published = dates[indices[i]].date().isoformat()
        url=f'https://example.invalid/synthetic/{i+1:03d}'
        text=f'SYNTHETIC TEST ARTICLE (NOT REAL NEWS). {title}. {summary} '+\
             'This text exists only to test collection, economic event extraction, time alignment, and estimation code.'
        rows.append(dict(article_id=hashlib.sha256(url.encode()).hexdigest()[:16],
                         company='NVIDIA', source='SYNTHETIC DEMO', source_type='synthetic_fixture',
                         title=title,url=url,published_date=published,
                         published_time_quality='date_only_synthetic',text=text,
                         text_chars=len(text),retrieved_utc='not_applicable',synthetic=True))
    write_csv(INPUTS/'demo_articles.csv', rows)
    rng=np.random.default_rng(cfg['analysis']['random_seed'])
    idx=pd.bdate_range('2026-07-27','2026-11-13')
    # Random walk prices, no real market data, no deliberately planted predictive alpha.
    common=rng.normal(0.0004,0.012,len(idx))
    qqq=100*np.exp(np.cumsum(common))
    nvda=120*np.exp(np.cumsum(common*1.6+rng.normal(0,0.013,len(idx))))
    prices=[{'date':d.date().isoformat(),'NVDA_close':round(float(n),6),
             'QQQ_close':round(float(q),6), 'source':'SYNTHETIC_DEMO'}
            for d,n,q in zip(idx,nvda,qqq)]
    write_csv(INPUTS/'demo_prices.csv',prices)
    message(f'Created clearly labeled synthetic demo fixtures: {len(rows)} articles, {len(prices)} trading-day stand-ins.')

if __name__ == '__main__':
    main()
