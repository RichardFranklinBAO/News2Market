"""News2Market: select one company, click one button, or run one CLI command.

python -m news2market --web
python -m news2market --ticker AAPL --news-days 30 --price-years 5
"""
from __future__ import annotations
import argparse
import json
from .core import run_pipeline, validate_options


def main():
    p=argparse.ArgumentParser(description="News2Market: three-company local research workbench")
    p.add_argument("--web",action="store_true",help="Open the local interactive dashboard")
    p.add_argument("--ticker",default="NVDA",choices=["NVDA","AAPL","GOOGL"])
    p.add_argument("--news-days",type=int,default=30,choices=[14,30,60,90])
    p.add_argument("--price-years",type=int,default=5,choices=[1,3,5])
    p.add_argument("--max-news",type=int,default=10,choices=[5,10,15])
    p.add_argument("--price-mode",default="auto",choices=["auto","nasdaq_csv"])
    p.add_argument("--use-proxy",action="store_true",help="Use your configured HTTPS_PROXY, not to bypass access restrictions")
    p.add_argument("--local-llm",action="store_true",help="Optional local Ollama Qwen2.5 1.5B (slow and unvalidated)")
    p.add_argument("--port",type=int,default=8765)
    args=p.parse_args()
    if args.web:
        from .web import start_server
        start_server(args.port)
        return
    o=validate_options(ticker=args.ticker,news_days=args.news_days,
         price_years=args.price_years,max_news=args.max_news,
         price_mode=args.price_mode,use_proxy=args.use_proxy,local_llm=args.local_llm)
    report=run_pipeline(o)
    print(json.dumps({"status":report["status"],"run":report["run_folder"],
        "news_count":report.get("news",{}).get("count"),
        "price_sessions":report.get("prices",{}).get("audit",{}).get("matched_sessions"),
        "regression":report.get("returns",{}).get("status")},indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
