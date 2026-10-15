"""Fetchers for official and market data. Standard library only.

Sources
  - US Treasury daily par yield curve (nominal + real)      home.treasury.gov
  - TreasuryDirect auction announcements and results       treasurydirect.gov TA_WS
  - Treasury buyback operations                            api.fiscaldata.treasury.gov
  - Effective fed funds rate and target range              markets.newyorkfed.org
  - FOMC meeting calendar, press releases, speeches        federalreserve.gov
  - 30-day fed funds futures (CBOT ZQ), MOVE index          Yahoo Finance chart API
  - News headlines, filtered to a verified-source list     Google News RSS
"""
from __future__ import annotations

import calendar
import csv
import io
import json
import re
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

# A full browser UA string makes Yahoo demand cookies and answer 429; the bare token works everywhere.
UA = "Mozilla/5.0"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def _ssl_context() -> ssl.SSLContext:
    """Verified TLS even on python.org macOS builds that ship without root certificates."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    if sys.platform == "darwin" and not ctx.get_ca_certs():
        pem = CACHE_DIR / "macos-roots.pem"
        if not pem.exists() or time.time() - pem.stat().st_mtime > 30 * 86400:
            out = subprocess.run(["security", "find-certificate", "-a", "-p",
                                  "/System/Library/Keychains/SystemRootCertificates.keychain"],
                                 capture_output=True, check=True).stdout
            pem.write_bytes(out)
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


_SSL = _ssl_context()


def http_get(url: str, timeout: float = 25, ua: str = UA) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
        return resp.read()


_cache: dict = {}
_cache_lock = threading.Lock()


def cached(key, ttl: float, fn):
    """In-memory TTL cache. Concurrent misses may fetch twice; that is harmless."""
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


# ---------------------------------------------------------------------------
# Treasury par yield curve
# ---------------------------------------------------------------------------
# (label, years to maturity). 1.5M exists only since 2025, so it is left off the chart.
TENORS = [("1M", 1 / 12), ("2M", 2 / 12), ("3M", 0.25), ("4M", 4 / 12), ("6M", 0.5),
          ("1Y", 1), ("2Y", 2), ("3Y", 3), ("5Y", 5), ("7Y", 7), ("10Y", 10),
          ("20Y", 20), ("30Y", 30)]
REAL_TENORS = ["5Y", "7Y", "10Y", "20Y", "30Y"]

_YC_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           "daily-treasury-rates.csv/{y}/all?type={t}&field_tdr_date_value={y}&page&_format=csv")


def _norm_tenor(header: str):
    h = header.strip().upper().replace("MONTH", "MO").replace("YEAR", "YR")
    m = re.match(r"([\d.]+)\s*(MO|YR)", h)
    if not m:
        return None
    n, unit = m.groups()
    return f"{n}{'M' if unit == 'MO' else 'Y'}"


def _parse_curve_csv(text: str) -> dict:
    rows = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            d = datetime.strptime(row["Date"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        vals = {}
        for key, val in row.items():
            if key == "Date" or not val or val == "N/A":
                continue
            tenor = _norm_tenor(key)
            if tenor:
                try:
                    vals[tenor] = float(val)
                except ValueError:
                    pass
        rows[d] = vals
    return rows


def year_curve(year: int, real: bool = False) -> dict:
    """{date: {tenor: yield%}} for one calendar year. Past years are cached on disk."""
    kind = "daily_treasury_real_yield_curve" if real else "daily_treasury_yield_curve"
    path = CACHE_DIR / f"yc_{'real' if real else 'nom'}_{year}.csv"
    if year < date.today().year and path.exists():
        return _parse_curve_csv(path.read_text())

    def fetch():
        text = http_get(_YC_URL.format(y=year, t=kind)).decode("utf-8", "replace")
        if year < date.today().year and "Date" in text[:20]:
            path.write_text(text)
        return _parse_curve_csv(text)

    return cached(("yc", year, real), 1200, fetch)


def curve_series(years, real: bool = False) -> dict:
    out = {}
    for y in sorted(set(years)):
        try:
            out.update(year_curve(y, real))
        except Exception:
            if y == date.today().year:
                raise
    return out


def on_or_before(series: dict, d: date):
    """Latest observation on or before d, or (None, None)."""
    best = None
    for k in series:
        if k <= d and (best is None or k > best):
            best = k
    return (best, series[best]) if best else (None, None)


# ---------------------------------------------------------------------------
# News (Google News RSS, verified sources only)
# ---------------------------------------------------------------------------
VERIFIED_SOURCES = {
    "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "wsj.com": "WSJ",
    "ft.com": "Financial Times", "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch",
    "barrons.com": "Barron's", "apnews.com": "AP", "nytimes.com": "New York Times",
    "washingtonpost.com": "Washington Post", "economist.com": "The Economist",
    "axios.com": "Axios", "federalreserve.gov": "Federal Reserve",
    "treasury.gov": "US Treasury", "newyorkfed.org": "New York Fed",
    "cbo.gov": "CBO", "bls.gov": "BLS", "bea.gov": "BEA", "cmegroup.com": "CME Group",
}


def verified_name(url: str):
    host = urllib.parse.urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for dom, name in VERIFIED_SOURCES.items():
        if host == dom or host.endswith("." + dom):
            return name
    return None


def google_news(query: str, after: date | None = None, before: date | None = None,
                when: str | None = None, verified_only: bool = True) -> list:
    q = query
    if after:
        q += f" after:{after.isoformat()}"
    if before:
        q += f" before:{before.isoformat()}"
    if when:
        q += f" when:{when}"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})

    def fetch():
        root = ET.fromstring(http_get(url))
        items = []
        for it in root.iter("item"):
            src = it.find("source")
            src_url = src.get("url", "") if src is not None else ""
            src_text = (src.text or "") if src is not None else ""
            name = verified_name(src_url)
            if verified_only and not name:
                continue
            title = unescape(it.findtext("title") or "").strip()
            if src_text and title.endswith(" - " + src_text):
                title = title[: -len(src_text) - 3]
            try:
                dt = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                dt = None
            items.append({"title": title, "source": name or src_text, "url": it.findtext("link"),
                          "published": dt.isoformat() if dt else None,
                          "date": dt.date().isoformat() if dt else None})
        return items

    return cached(("gn", url, verified_only), 900, fetch)


def rss(url: str, limit: int = 10) -> list:
    def fetch():
        root = ET.fromstring(http_get(url))
        out = []
        for it in list(root.iter("item"))[:limit]:
            try:
                dt = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                dt = None
            out.append({"title": unescape(it.findtext("title") or "").strip(),
                        "url": it.findtext("link"), "date": dt.date().isoformat() if dt else None})
        return out

    return cached(("rss", url), 900, fetch)


FED_PRESS_RSS = "https://www.federalreserve.gov/feeds/press_all.xml"
FED_SPEECH_RSS = "https://www.federalreserve.gov/feeds/speeches.xml"


# ---------------------------------------------------------------------------
# Fed: policy rate, calendar, futures
# ---------------------------------------------------------------------------
def effr_history(n: int = 90) -> list:
    """[{date, rate, lo, hi}] newest first, from the New York Fed."""
    def fetch():
        data = json.loads(http_get(
            f"https://markets.newyorkfed.org/api/rates/unsecured/effr/last/{n}.json"))
        return [{"date": r["effectiveDate"], "rate": r["percentRate"],
                 "lo": r.get("targetRateFrom"), "hi": r.get("targetRateTo")}
                for r in data["refRates"]]
    return cached(("effr", n), 1800, fetch)


FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}


def fomc_meetings() -> list:
    """Scheduled FOMC meetings as [{date: decision day ISO, label, sep}], sorted."""
    def fetch():
        html = http_get(FOMC_URL).decode("utf-8", "replace")
        parts = re.split(r"(\d{4}) FOMC Meetings", html)
        out = []
        for i in range(1, len(parts) - 1, 2):
            year, body = int(parts[i]), parts[i + 1]
            pairs = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?'
                               r'fomc-meeting__date[^>]*>([^<]+)<', body, re.S)
            for mon, days in pairs:
                m = re.match(r"^\s*(\d{1,2})(?:-(\d{1,2}))?(\*)?\s*$", days)
                if not m:
                    continue  # notation votes, unscheduled meetings
                months = [_MONTHS.get(x.strip()[:3].lower()) for x in mon.split("/")]
                if None in months:
                    continue
                start, end = int(m.group(1)), int(m.group(2) or m.group(1))
                end_month = months[-1] if (len(months) > 1 and end < start) else months[0]
                try:
                    d = date(year, end_month, end)
                except ValueError:
                    continue
                out.append({"date": d.isoformat(), "label": f"{mon.strip()} {days.strip().rstrip('*')}, {year}",
                            "sep": bool(m.group(3))})
        out.sort(key=lambda x: x["date"])
        uniq = {x["date"]: x for x in out}
        return list(uniq.values())
    return cached("fomc", 6 * 3600, fetch)


_MONTH_CODES = "FGHJKMNQUVXZ"


def zq_symbol(y: int, m: int) -> str:
    return f"ZQ{_MONTH_CODES[m - 1]}{y % 100:02d}.CBT"


def _parse_chart(res: dict) -> dict:
    meta = res["meta"]
    off = meta.get("gmtoffset", 0)
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    hist = [(datetime.fromtimestamp(t + off, tz=timezone.utc).date(), c)
            for t, c in zip(res.get("timestamp") or [], closes) if c is not None]
    t = meta.get("regularMarketTime")
    return {"price": meta.get("regularMarketPrice"), "hist": hist,
            "time": datetime.fromtimestamp(t, tz=timezone.utc).isoformat() if t else None}


def yahoo_chart(symbol: str, range_: str = "3mo") -> dict:
    """{'price': last, 'hist': [(date, close)], 'time': iso} or raises."""
    def fetch():
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
               f"?range={range_}&interval=1d")
        return _parse_chart(json.loads(http_get(url, timeout=15))["chart"]["result"][0])
    return cached(("yahoo", symbol, range_), 600, fetch)


def yahoo_spark(symbols: list, range_: str = "3mo") -> dict:
    """Batch version of yahoo_chart: {symbol: chart}. Symbols Yahoo does not know are left out."""
    def fetch():
        out = {}
        for i in range(0, len(symbols), 20):
            chunk = ",".join(symbols[i:i + 20])
            url = (f"https://query1.finance.yahoo.com/v7/finance/spark?symbols={urllib.parse.quote(chunk, safe=',')}"
                   f"&range={range_}&interval=1d")
            for r in json.loads(http_get(url, timeout=20))["spark"]["result"]:
                try:
                    out[r["symbol"]] = _parse_chart(r["response"][0])
                except (KeyError, IndexError, TypeError):
                    pass
        return out
    return cached(("spark", tuple(symbols), range_), 600, fetch)


# ---------------------------------------------------------------------------
# FRED (St. Louis Fed). Its bot filter rejects browser-like UAs, so send a plain one.
# ---------------------------------------------------------------------------
def fred(series_id: str, start: date) -> list:
    """[(date, value)] ascending, from the public fredgraph CSV (no API key)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start.isoformat()}"

    def fetch():
        text = http_get(url, timeout=40, ua="curve-desk/1.0").decode("utf-8", "replace")
        out = []
        for row in list(csv.reader(io.StringIO(text)))[1:]:
            if len(row) >= 2 and row[1] not in ("", "."):
                try:
                    out.append((date.fromisoformat(row[0]), float(row[1])))
                except ValueError:
                    pass
        return out
    return cached(("fred", series_id, start), 6 * 3600, fetch)


# ---------------------------------------------------------------------------
# Auctions and buybacks
# ---------------------------------------------------------------------------
TD = "https://www.treasurydirect.gov/TA_WS/securities"


def td_upcoming() -> list:
    return cached("td_up", 900, lambda: json.loads(http_get(f"{TD}/upcoming?format=json")))


def td_auctioned(days: int = 420) -> list:
    return cached(("td_auc", days), 1800,
                  lambda: json.loads(http_get(f"{TD}/auctioned?format=json&days={days}", timeout=40)))


def td_pdf(year: str, filename: str):
    if not filename:
        return None
    return f"https://www.treasurydirect.gov/instit/annceresult/press/preanre/{year}/{filename}"


def buyback_operations(n: int = 30) -> list:
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
           f"buybacks_operations?sort=-operation_date&page%5Bsize%5D={n}")
    return cached(("bb", n), 1800, lambda: json.loads(http_get(url, timeout=40))["data"])


# ---------------------------------------------------------------------------
# Money markets
# ---------------------------------------------------------------------------
def sofr_history(n: int = 30) -> list:
    """[{date, rate, p1, p99, volume_bn}] newest first, from the New York Fed."""
    def fetch():
        data = json.loads(http_get(f"https://markets.newyorkfed.org/api/rates/secured/sofr/last/{n}.json"))
        return [{"date": r["effectiveDate"], "rate": r["percentRate"], "p1": r.get("percentPercentile1"),
                 "p99": r.get("percentPercentile99"), "volume_bn": r.get("volumeInBillions")} for r in data["refRates"]]
    return cached(("sofr", n), 1800, fetch)


def tga_history(n: int = 40) -> list:
    """Treasury General Account closing balance, [(date, $bn)] newest first, from the Daily Treasury Statement."""
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
           f"?sort=-record_date&page%5Bsize%5D={n * 4}&fields=record_date,account_type,open_today_bal,close_today_bal")

    def fetch():
        out = []
        for r in json.loads(http_get(url, timeout=40))["data"]:
            if "Closing Balance" in r["account_type"] and "TGA" in r["account_type"]:
                v = r["close_today_bal"] if r["close_today_bal"] not in (None, "null") else r["open_today_bal"]
                try:
                    out.append((date.fromisoformat(r["record_date"]), float(v) / 1000))
                except (TypeError, ValueError):
                    pass
        return out
    return cached("tga", 3600, fetch)


def debt_composition(months: int = 14) -> list:
    """Marketable debt by class from the Monthly Statement of the Public Debt: [{date, bills, total}] in $mn, newest first."""
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_1"
           f"?sort=-record_date&page%5Bsize%5D={months * 25}&fields=record_date,security_type_desc,security_class_desc,total_mil_amt")

    def fetch():
        by = {}
        for r in json.loads(http_get(url, timeout=40))["data"]:
            d = by.setdefault(r["record_date"], {})
            if r["security_type_desc"] == "Marketable" and r["security_class_desc"] == "Bills":
                d["bills"] = float(r["total_mil_amt"])
            if r["security_type_desc"] == "Total Marketable":
                d["total"] = float(r["total_mil_amt"])
        return [{"date": k, **v} for k, v in sorted(by.items(), reverse=True) if "bills" in v and "total" in v]
    return cached("mspd", 6 * 3600, fetch)
