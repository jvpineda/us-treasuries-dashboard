"""Build a static copy of the dashboard for GitHub Pages.

    python3 build_static.py            # writes ./site

Every API route the page calls is computed once and saved as JSON under site/data/. The page detects the static
build (config.js) and reads those files instead of calling the local server. The preset windows (1D to 1Y) are
included; custom dates and Claude's sourced read need the local server.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import analytics as A
import sources as S
from server import _fed

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
HORIZONS = ["1D", "1W", "1M", "3M", "1Y"]
REQUIRED = {"strip", "curve-1Y", "story-1Y"}


def jobs():
    yield "strip", A.strip
    yield "health", A.health
    yield "matrix", A.matrix
    yield "history", A.curve_history
    yield "money", A.money_markets
    yield "fed", _fed
    yield "auctions", A.auctions_cached
    yield "treasury-news", A.treasury_news
    for h in HORIZONS:
        yield f"curve-{h}", (lambda h=h: A.curve_analysis(h))
        yield f"story-{h}", (lambda h=h: A.story_view(h))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    (OUT / "data").mkdir()
    failed = []
    for name, fn in jobs():
        t = time.time()
        try:
            data = fn()
            (OUT / "data" / f"{name}.json").write_text(json.dumps(data, default=str))
            print(f"ok   {name:16s} {time.time() - t:5.1f}s")
        except Exception:
            failed.append(name)
            print(f"FAIL {name}", file=sys.stderr)
            traceback.print_exc()
    built = datetime.now(timezone.utc).isoformat(timespec="minutes")
    (OUT / "data" / "meta.json").write_text(json.dumps({"built_at": built, "failed": failed}))
    (OUT / "config.js").write_text("window.UST_STATIC = true;\n")
    html = (OUT / "index.html").read_text()
    (OUT / "index.html").write_text(html.replace('<script src="sources.js"></script>',
                                                 '<script src="config.js"></script>\n<script src="sources.js"></script>'))
    (OUT / ".nojekyll").write_text("")
    (OUT / ".vercelignore").write_text(".env*\n.vercel\n")
    if REQUIRED & set(failed):
        sys.exit(f"Required data failed: {sorted(REQUIRED & set(failed))}")
    print(f"Built {OUT} at {built}; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
