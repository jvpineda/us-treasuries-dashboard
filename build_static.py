"""Build a static copy of the dashboard for GitHub Pages.

    python3 build_static.py            # writes ./site

Every API route the page calls is computed once and saved as JSON under site/data/. The page detects the static
build (config.js) and reads those files instead of calling the local server. The preset windows (1D to 1Y) are
included; custom dates and Claude's sourced read need the local server.
"""
from __future__ import annotations

import html as H
import json
import os
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
SITE_URL = os.environ.get("SITE_URL", "https://ustdashboard.vercel.app/")
# Google Search Console ownership check (public value from the "HTML tag" method); set the repo variable to enable.
GOOGLE_VERIFY = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
DESC_FALLBACK = ("Daily US Treasury yield curve briefing: why the curve moved, Fed rate expectations by meeting, "
                 "funding markets and Treasury auction supply, explained in plain language.")


def seo(html: str, built: str) -> str:
    """What search engines and link previews see: description, canonical URL, share tags, structured data, and the
    day's executive summary written into the page so it is readable before any script runs."""
    try:
        st = json.loads((OUT / "data" / "story-1Y.json").read_text())["story"]
        se, rates = st["summary_exec"], {r["key"]: r for r in st["exec"]["rates"]}
        asof = json.loads((OUT / "data" / "strip.json").read_text())["asof"]
    except Exception:
        se, rates, asof = None, {}, built[:10]
    desc = (se["headline"] + " " + (se["sentences"][0] if se["sentences"] else "")) if se else DESC_FALLBACK
    desc = desc if len(desc) <= 300 else desc[:297].rsplit(" ", 1)[0] + "…"
    title = "US Treasuries Dashboard: yield curve, Fed pricing and auctions, explained daily"
    ld = {
        "@context": "https://schema.org", "@type": "WebApplication", "name": "US Treasuries Dashboard",
        "url": SITE_URL, "applicationCategory": "FinanceApplication", "operatingSystem": "Any",
        "description": DESC_FALLBACK, "dateModified": built, "isAccessibleForFree": True,
        "author": {"@type": "Person", "name": "JV Pineda"},
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    head = f"""<meta name="description" content="{H.escape(desc)}">
<link rel="canonical" href="{SITE_URL}">
<meta name="robots" content="index, follow, max-snippet:-1">
<meta property="og:type" content="website">
<meta property="og:site_name" content="US Treasuries Dashboard">
<meta property="og:title" content="{H.escape(title)}">
<meta property="og:description" content="{H.escape(desc)}">
<meta property="og:url" content="{SITE_URL}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{H.escape(title)}">
<meta name="twitter:description" content="{H.escape(desc)}">
{f'<meta name="google-site-verification" content="{H.escape(GOOGLE_VERIFY)}">' if GOOGLE_VERIFY else ''}
<script type="application/ld+json">{json.dumps(ld)}</script>"""
    html = html.replace("<title>US Treasuries Dashboard</title>", f"<title>{H.escape(title)}</title>\n{head}", 1)
    if se:
        nums = " · ".join(f"{k} {rates[k]['now']:.2f}% ({rates[k]['chg_bp']:+.0f}bp, 1Y)" for k in ("2Y", "10Y", "30Y") if k in rates)
        static = (f'<div id="storyBody"><p class="eyebrow">Executive summary · 1 year to the {H.escape(asof)} close</p>'
                  f'<h2 class="headline">{H.escape(se["headline"])}</h2>'
                  f'<p class="exec-p">{H.escape(" ".join(se["sentences"]))}</p>'
                  f'<p class="hint">{H.escape(nums)}</p></div>')
        html = html.replace('<div id="storyBody"><p class="muted">Building the executive summary…</p></div>', static, 1)
    return html


def crawl_files(built: str):
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><lastmod>{built[:10]}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
        "</urlset>\n")


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


def news_check():
    """Log whether the news feed answers from this machine (it can block cloud servers)."""
    import urllib.request
    url = "https://news.google.com/rss/search?q=%22Treasury+yields%22+when:2d&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": S.UA})
        with urllib.request.urlopen(req, timeout=20, context=S._SSL) as r:
            body = r.read()
            print(f"news check: HTTP {r.status}, {len(body)} bytes, {body.count(b'<item>')} items, final URL {r.geturl()[:80]}")
    except Exception as e:
        print(f"news check: failed: {e!r}"[:300])


def main():
    news_check()
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
    html = html.replace('<script src="sources.js"></script>', '<script src="config.js"></script>\n<script src="sources.js"></script>')
    (OUT / "index.html").write_text(seo(html, built))
    crawl_files(built)
    (OUT / ".nojekyll").write_text("")
    (OUT / ".vercelignore").write_text(".env*\n.vercel\n")
    if REQUIRED & set(failed):
        sys.exit(f"Required data failed: {sorted(REQUIRED & set(failed))}")
    print(f"Built {OUT} at {built}; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
