"""Resolve US SEC-listed tickers to company name and CIK; never infer ticker->site."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from common import INPUTS, RESULTS, config, sec_ua, fetch_json, json_dump, message

SEC_MAPPING='https://www.sec.gov/files/company_tickers.json'

def resolve_from_mapping(symbol, mapping):
    symbol=symbol.upper().strip()
    for obj in (mapping.values() if isinstance(mapping,dict) else mapping):
        if str(obj.get('ticker','')).upper() == symbol:
            return {'ticker':symbol,'name':obj['title'],'cik':str(int(obj['cik_str'])).zfill(10),'resolution':'SEC ticker mapping'}
    raise ValueError(f'Ticker {symbol} absent from SEC ticker mapping. Only supported US-listed equity tickers are expected; do not guess company. Check delistings/share classes.')

def main():
    c=config(); ctx=c['_context']; ticker=c['project']['ticker']; source=ctx['source']
    if ctx['mode']=='demo':
        if ticker!='NVDA': raise RuntimeError('Synthetic demo only provides NVDA fixtures; use --ticker NVDA --mode demo')
        obj={'ticker':'NVDA','name':'NVIDIA CORPORATION','cik':'0001045810','resolution':'SYNTHETIC_DEMO hardcoded identity'}
    elif ctx.get('company_name') and ctx.get('cik'):
        obj={'ticker':ticker,'name':ctx['company_name'],'cik':str(int(ctx['cik'])).zfill(10),'resolution':'USER-SUPPLIED UNVERIFIED: confirm SEC identity'}
    elif source=='nvidia':
        if ticker!='NVDA': raise RuntimeError('--source nvidia is only valid for NVDA; never assign NVIDIA news to another ticker')
        obj={'ticker':'NVDA','name':'NVIDIA CORPORATION','cik':'0001045810','resolution':'pinned NVIDIA-only profile, SEC mapping not contacted'}
    else:
        cache=INPUTS/'cache'/'company_tickers.json'
        if cache.exists():
            import json
            mapping=json.loads(cache.read_text(encoding='utf-8'))
            message(f'Using cached SEC ticker map: {cache}')
        else:
            mapping=fetch_json(SEC_MAPPING,sec_ua())
            cache.parent.mkdir(parents=True,exist_ok=True)
            json_dump(cache,mapping)
        obj=resolve_from_mapping(ticker,mapping)
    obj.update({'resolved_utc':datetime.now(timezone.utc).isoformat(), 'sec_ticker_map_url':SEC_MAPPING})
    json_dump(RESULTS/'00_company.json',obj)
    message(f"Company: {obj['ticker']} | {obj['name']} | CIK {obj['cik']} ({obj['resolution']})")

if __name__=='__main__': main()
