"""US Treasuries Dashboard: local US Treasuries dashboard.

    python3 server.py            # http://127.0.0.1:8765
    PORT=9000 python3 server.py --open
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ai
import analytics as A
import sources as S

STATIC = Path(__file__).resolve().parent / "static"
HORIZON_RX = re.compile(r"^(1D|1W|1M|3M|1Y|\d{4}-\d{2}-\d{2})$")


def _horizon(q):
    h = (q.get("h") or ["1D"])[0]
    if not HORIZON_RX.match(h):
        raise ValueError("Horizon must be 1D, 1W, 1M, 3M, 1Y or a date (YYYY-MM-DD).")
    return h


def _fed():
    def build():
        fv = A.fed_cached()
        return {**fv, "context": A.fed_context(fv)}
    return S.cached("fed_all", 300, build)


def _h(q):
    return _horizon(q)


GET_ROUTES = {
    "/api/strip": lambda q: S.cached("strip", 300, A.strip),
    "/api/matrix": lambda q: S.cached("matrix", 600, A.matrix),
    "/api/curve": lambda q: S.cached(("curve", _h(q)), 600, lambda: A.curve_analysis(_h(q))),
    "/api/story": lambda q: S.cached(("story", _h(q)), 900, lambda: A.story_view(_h(q))),
    "/api/history": lambda q: S.cached("history", 1200, A.curve_history),
    "/api/auctions": lambda q: A.auctions_cached(),
    "/api/treasury-news": lambda q: S.cached("tnews", 900, A.treasury_news),
    "/api/fed": lambda q: _fed(),
    "/api/ai/status": lambda q: ai.status(),
    "/api/money": lambda q: S.cached("money", 900, A.money_markets),
    "/api/health": lambda q: S.cached("health", 600, A.health),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "USTDashboard/1.0"

    def log_message(self, fmt, *args):
        if args and "/api/" in str(args[0]):
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _run(self, fn):
        try:
            self._json(200, fn())
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            self._json(502, {"error": f"Upstream data source failed: {e}"})

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in GET_ROUTES:
            return self._run(lambda: GET_ROUTES[url.path](q))
        rel = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
        f = (STATIC / rel).resolve()
        if not str(f).startswith(str(STATIC)) or not f.is_file():
            self.send_error(404)
            return
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/ai":
            q = parse_qs(url.query)
            return self._run(lambda: ai.interpret(S.cached(("story", _h(q)), 900, lambda: A.story_view(_h(q)))))
        self.send_error(404)


def main():
    port = int(os.environ.get("PORT", "8765"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    link = f"http://127.0.0.1:{port}"
    print(f"US Treasuries Dashboard running at {link}  (Ctrl+C to stop)")
    if "--open" in sys.argv:
        webbrowser.open(link)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
