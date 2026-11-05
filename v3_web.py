"""Local-only HTTP dashboard. No external hosting, accounts, or paid services."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs

from v3_core import ROOT, supported_companies, validate_options, run_pipeline, price_status, import_nasdaq_csv, _reuse_previous_project_csv, lm_dictionary_status

UI_HTML=(ROOT/"v3_ui"/"index.html")
LOCK=threading.Lock()
STATE={"status":"idle","message":"Choose a company to start","lines":[],"report":None}


def snapshot():
    with LOCK:
        return {"status":STATE["status"],"message":STATE["message"],
                "lines":list(STATE["lines"][-35:]),"report":STATE["report"]}


def worker(opt):
    def log(message):
        with LOCK:
            STATE["message"]=str(message)
            STATE["lines"].append(str(message)[:250])
            if len(STATE["lines"])>120:STATE["lines"]=STATE["lines"][-100:]
    try:
        report=run_pipeline(opt,log=log)
        with LOCK:
            STATE["report"]=report
            STATE["status"]="complete"
            STATE["message"]="Pipeline complete. Inspect measurements and audit warnings."
    except Exception as exc:
        with LOCK:
            STATE["status"]="failed"
            STATE["message"]=str(exc)[:600]
            STATE["lines"].append("FAILED: "+str(exc)[:350])


class LocalHandler(BaseHTTPRequestHandler):
    server_version="News2MarketLocal/3.0"

    def _send(self,body,status=200,mime="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self,content,status=200):
        self._send(json.dumps(content,default=str,ensure_ascii=False).encode("utf-8"),status)

    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":
            self._send(UI_HTML.read_bytes(),mime="text/html; charset=utf-8")
        elif path=="/api/profiles":
            self._json({"companies":supported_companies()})
        elif path=="/api/state":
            self._json(snapshot())
        elif path=="/api/prices":
            query=parse_qs(urlparse(self.path).query)
            ticker=query.get("ticker",["NVDA"])[0].upper()
            try:
                _reuse_previous_project_csv(ticker,log=lambda msg:None)
                _reuse_previous_project_csv("QQQ",log=lambda msg:None)
                self._json({**price_status(ticker), "lm_dictionary": lm_dictionary_status()})
            except ValueError as exc:
                self._json({"error":str(exc)},400)
        else:
            self._json({"error":"not found"},404)

    def do_POST(self):
        path=urlparse(self.path).path
        if path not in ("/api/run","/api/import-price"):
            self._json({"error":"not found"},404);return
        # Localhost-only service, protect write endpoints against remote-web origins.
        port=self.server.server_port
        allowed={f"http://127.0.0.1:{port}",f"http://localhost:{port}"}
        origin=self.headers.get("Origin","").rstrip("/")
        referer=self.headers.get("Referer","")
        if (origin and origin not in allowed) or (referer and not any(
            referer==base or referer.startswith(base+"/") for base in allowed)):
            self._json({"error":"Unexpected request origin"},403);return
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<2 or length>2_700_000:raise ValueError("Request payload too large or empty")
            body=json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body,dict):raise ValueError("Invalid JSON request")
            if path=="/api/import-price":
                with LOCK:
                    if STATE["status"]=="running":
                        self._json({"error":"Cannot import prices while a research job is running"},409);return
                if set(body)-{"symbol","csv_text","confirmed_nasdaq"}:
                    raise ValueError("Unexpected import fields")
                result=import_nasdaq_csv(body.get("symbol"),body.get("csv_text"),body.get("confirmed_nasdaq") is True)
                self._json({"status":"imported","result":result},201)
                return
            opt=validate_options(**{k:v for k,v in body.items() if k in
               {"ticker","news_days","price_years","max_news","price_mode","use_proxy","local_llm"}})
        except (ValueError,TypeError,UnicodeError) as exc:
            self._json({"error":str(exc)},400);return
        with LOCK:
            if STATE["status"]=="running":
                self._json({"error":"A job is already running"},409);return
            STATE.update({"status":"running","message":"Initializing","lines":[],"report":None})
        th=threading.Thread(target=worker,args=(opt,),daemon=True)
        th.start()
        self._json({"status":"started","ticker":opt["ticker"]},202)

    def log_message(self,format,*args):
        # Avoid filling the terminal with every polling request.
        if not (self.path=="/api/state" and args and str(args[1])=="200"):
            super().log_message(format,*args)


def start_server(port=8765):
    port=int(port)
    if not 1024<=port<=65535:raise ValueError("Port must be 1024..65535")
    if not UI_HTML.exists():raise FileNotFoundError(f"Missing dashboard: {UI_HTML}")
    server=ThreadingHTTPServer(("127.0.0.1",port),LocalHandler)
    url=f"http://127.0.0.1:{port}/"
    print(f"News2Market v3 local dashboard: {url}\nPress Ctrl+C to stop.",flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":start_server()
