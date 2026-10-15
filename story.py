"""Themes and news for the near-term story (the narrative itself is in narrative.py).

  - Themes: rank real-world themes by verified news volume in the window and check each one's expected
    fingerprint on the curve against what the curve actually did.
  - Surprises: verified headlines tallied as hotter or cooler than forecast.
  - Watch list: the next FOMC meeting and coupon auctions.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import sources as S

# expect: curve component -> sign the theme should push it. Components: d2, d10, d30, real10, be10, be5, tp
THEMES = [
    {"key": "ai_capex", "name": "AI investment boom",
     "query": '("AI spending" OR "AI capex" OR "data center" OR "data centers" OR hyperscalers OR "AI investment" OR "AI boom")',
     "channel": "Growth and real rates", "expect": {"real10": +1},
     "mechanism": "Data-center and chip spending keeps investment and power demand strong. That lifts the economy's "
                  "neutral rate, so real yields rise; funding the build-out also adds corporate debt that competes "
                  "with Treasuries for buyers."},
    {"key": "ai_disruption", "name": "AI disruption and the SaaSpocalypse",
     "query": '(SaaS OR "software stocks" OR "AI disruption" OR "AI layoffs" OR "white-collar" OR "AI job cuts")',
     "channel": "Labor slack and risk appetite", "expect": {"d2": -1},
     "mechanism": "AI agents are replacing work that software seats and white-collar jobs used to do. Over time that "
                  "is disinflationary: softer hiring, slower wage growth, weaker incumbents. For bonds it argues for "
                  "a lower expected Fed path and haven demand at the long end."},
    {"key": "tariffs", "name": "Tariffs and the cost of living",
     "query": '(tariff OR tariffs OR "cost of living" OR "grocery prices" OR affordability)',
     "channel": "Goods inflation", "expect": {"be10": +1, "d2": +1},
     "mechanism": "Import taxes pass through to shelf prices. Higher goods inflation keeps the Fed from easing and "
                  "lifts inflation compensation, so the front end and breakevens rise."},
    {"key": "energy", "name": "Oil, Iran and energy prices",
     "query": '(oil OR "gas prices" OR gasoline OR Iran OR OPEC OR "energy prices")',
     "channel": "Headline inflation and the Fed", "expect": {"be5": +1, "d2": +1},
     "mechanism": "An energy shock raises headline inflation and near-term inflation expectations, lifting "
                  "short-dated breakevens and the front end. If it starts to hurt demand, the long end rallies."},
    {"key": "deficits", "name": "Deficits and Treasury supply",
     "query": '(deficit OR "national debt" OR "Treasury supply" OR "term premium" OR "bond vigilantes" OR "debt ceiling") Treasury',
     "channel": "Pay for lending long", "expect": {"d30": +1, "slope": +1},
     "mechanism": "Deficits near $2 trillion mean heavy government borrowing. Investors want to be paid more to lend "
                  "for 10 to 30 years, which lifts long-term yields more than short-term ones."},
    {"key": "jobs", "name": "Job market",
     "query": '(payrolls OR "jobs report" OR unemployment OR layoffs OR hiring) economy',
     "channel": "Growth and the Fed path", "expect": "jobs",
     "mechanism": "Hiring decides how much room the Fed has. A cooling job market pulls the expected Fed path and "
                  "the front end down; a tight one holds them up."},
    {"key": "housing", "name": "Housing affordability",
     "query": '("mortgage rates" OR "home prices" OR "housing market" OR "home sales")',
     "channel": "Consequence of long rates", "expect": {},
     "mechanism": "Mortgage rates track the 10Y plus a spread. Higher long yields freeze home sales and refinancing, "
                  "which feeds back into slower growth with a lag."},
    {"key": "global", "name": "Global bond selloff",
     "query": '(gilts OR "Japanese bond" OR JGB OR bunds OR "global bond") yields',
     "channel": "Global long-term rates", "expect": {"d30": +1},
     "mechanism": "Rising long-term yields in Japan, the UK and Europe give investors better returns at home, pulling "
                  "buyers away from Treasuries."},
    {"key": "fed_politics", "name": "Politics and Fed independence",
     "query": '("Fed independence" OR "Fed chair" OR midterms OR "White House" Fed)',
     "channel": "Inflation risk", "expect": {"be10": +1, "d30": +1},
     "mechanism": "Doubts about the Fed's independence raise the risk that inflation runs hot. That shows up in "
                  "inflation expectations, gold and long-term yields more than in short-term yields."},
]
YAHOO_GAUGES = {"SMH": "Chip stocks (SMH)", "IGV": "Software stocks (IGV)", "GC=F": "Gold", "^GSPC": "S&P 500"}

SURPRISES = [
    ("Inflation", '(CPI OR "consumer prices" OR PCE OR inflation) ("than expected" OR forecast OR forecasts OR estimates)'),
    ("Jobs", '(payrolls OR "jobs report" OR "job growth" OR unemployment) ("than expected" OR forecast OR estimates)'),
    ("Growth", '(GDP OR "retail sales" OR "consumer spending") ("than expected" OR forecast OR estimates)'),
]
HOT_RX = re.compile(r"hotter|\bhot\b|higher than expected|above (forecast|expectation|estimate)|\btops?\b|topped|\bbeats?\b"
                    r"|exceed|stronger|surg|accelerat|more than expected|unexpectedly (rose|rise|climb|jump)", re.I)
COOL_RX = re.compile(r"cooler|\bcool\b|softer|lower than expected|below (forecast|expectation|estimate)|\bmiss"
                     r"|weaker|\bslow|\beas(e|es|ed)\b|less than expected|unexpectedly (fell|fall|drop|declin)", re.I)
RATES_QUERY = '"Treasury yields" OR Treasuries OR "bond market"'
# Themes are counted only where coverage ties them to rates: the question is what moved bonds, not what trended.
RATES_LINK = ' (yields OR Treasuries OR bonds OR Fed OR "interest rates")'


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def _key(title):
    return re.sub(r"\W+", "", title.lower())[:90]


def _window_items(items, past, asof):
    lo, hi = (past - timedelta(days=1)).isoformat(), asof.isoformat()
    inside = [i for i in items if i.get("date") and lo <= i["date"] <= hi]
    after = [i for i in items if i.get("date") and i["date"] > hi]
    return inside, after


def gather(past: date, asof: date) -> dict:
    """All news the story needs, fetched in parallel: theme volumes, release surprises, rates headlines."""
    after, before = past - timedelta(days=1), max(asof, date.today()) + timedelta(days=1)
    jobs = [("theme", t["key"], t["query"] + RATES_LINK) for t in THEMES] + [("surprise", n, q) for n, q in SURPRISES] + \
           [("rates", "rates", RATES_QUERY)]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: _safe(S.google_news, j[2], after, before) or [], jobs))
    out = {"theme": {}, "surprise": {}, "rates": []}
    for (kind, key, _), items in zip(jobs, res):
        if kind == "rates":
            out["rates"] = items
        else:
            out[kind][key] = items
    return out


def surprise_tally(news: dict, past: date, asof: date) -> list:
    rows = []
    for name, _ in SURPRISES:
        inside, _ = _window_items(news["surprise"].get(name, []), past, asof)
        hot = [i for i in inside if HOT_RX.search(i["title"]) and not COOL_RX.search(i["title"])]
        cool = [i for i in inside if COOL_RX.search(i["title"]) and not HOT_RX.search(i["title"])]
        tilt = ("hotter" if len(hot) > 1.5 * len(cool) and len(hot) >= 2 else
                "cooler" if len(cool) > 1.5 * len(hot) and len(cool) >= 2 else "mixed")
        if name != "Inflation":
            tilt = {"hotter": "stronger", "cooler": "weaker"}.get(tilt, tilt)
        rows.append({"name": name, "hot": len(hot), "cool": len(cool), "tilt": tilt,
                     "examples": (hot if len(hot) >= len(cool) else cool)[:2]})
    return rows


def _dt(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def _yahoo_change(symbols, past):
    spark = _safe(S.yahoo_spark, list(symbols), "2y") or {}
    out = {}
    for sym in symbols:
        c = spark.get(sym)
        if not c or not c["hist"]:
            continue
        start = [(d, px) for d, px in c["hist"] if d <= past]
        if start:
            d0, p0 = start[-1]
            out[sym] = {"then": p0, "now": c["price"], "pct": round((c["price"] / p0 - 1) * 100, 1),
                        "then_date": _dt(d0), "now_date": _dt(c["hist"][-1][0])}
    return out


def _span(row, money="", unit=""):
    """'$59.8 (Oct 10, 2025) to $96.2 (Oct 6, 2026)' with the reading date of each value."""
    if not row:
        return "n/a"
    dec = row["decimals"]
    now = f"{money}{row['now']['value']:,.{dec}f}{unit} ({row['now']['period']})"
    if not row.get("then"):
        return now
    if row["then"]["period"] == row["now"]["period"]:
        return f"{now}, no new reading in the window"
    return f"{money}{row['then']['value']:,.{dec}f}{unit} ({row['then']['period']}) to {now}"


def _life_line(key, sc, yh):
    k = sc["by_key"]
    def mkt(sym, label):
        y = yh.get(sym)
        return f"{label} {y['pct']:+.1f}% ({y['then_date']} to {y['now_date']})" if y else f"{label} n/a"
    if key == "ai_capex":
        return f"{mkt('SMH', 'Chip stocks (SMH)')}; {mkt('^GSPC', 'S&P 500')}."
    if key == "ai_disruption":
        return f"{mkt('IGV', 'Software stocks (IGV)')} vs {mkt('SMH', 'chip stocks')}. Unemployment {_span(k.get('unrate'), unit='%')}."
    if key == "tariffs":
        return f"Core goods inflation {_span(k.get('core_goods'), unit='% y/y')}; headline CPI {_span(k.get('cpi'), unit='% y/y')}."
    if key == "energy":
        return f"WTI crude {_span(k.get('oil'), money='$')}; gasoline {_span(k.get('gas'), money='$', unit='/gal')}."
    if key == "deficits":
        return f"12-month federal deficit {_span(k.get('deficit'), money='$', unit='tn')}."
    if key == "jobs":
        return f"Unemployment {_span(k.get('unrate'), unit='%')}; payroll growth (3-month avg) {_span(k.get('payrolls'), unit='k/month')}."
    if key == "housing":
        return f"30-year mortgage rate {_span(k.get('mortgage'), unit='%')}."
    if key == "global":
        return f"10Y yields, monthly average: Japan {_span(k.get('jgb10'), unit='%')}; UK {_span(k.get('gilt10'), unit='%')}."
    if key == "fed_politics":
        return f"{mkt('GC=F', 'Gold')}; consumers' 1-year inflation expectation {_span(k.get('mich'), unit='%')}."
    return ""


COMP_LABEL = {"d2": "the 2Y yield", "d10": "the 10Y yield", "d30": "the 30Y yield", "real10": "the 10Y real yield",
              "be10": "10-year inflation expectations", "be5": "5-year inflation expectations",
              "slope": "the long end relative to the short end (30Y minus 2Y)"}


def _verdict(expect, comps):
    thr = max(3.0, 0.15 * abs(comps.get("d10") or 0))  # a "reaction" must be material relative to the whole move
    if not expect:
        return "Context", "This theme is a consequence of the move rather than a cause."
    agree, disagree, parts = 0, 0, []
    for comp, sign in expect.items():
        v = comps.get(comp)
        if v is None:
            continue
        if v * sign >= thr:
            agree += 1
            tag = "as this story predicts"
        elif v * sign <= -thr:
            disagree += 1
            tag = "the opposite of what it predicts"
        else:
            tag = "barely moved"
        parts.append(f"{COMP_LABEL[comp]} {'rose' if v > 0 else 'fell'} {abs(v):.0f}bp, {tag}" if tag != "barely moved"
                     else f"{COMP_LABEL[comp]} barely moved ({v:+.0f}bp)")
    if not parts:
        return "Unclear", "The curve data needed to test this story is not available for this window."
    evidence = "; ".join(parts)
    evidence = evidence[0].upper() + evidence[1:]
    if agree and not disagree:
        return "Priced", f"{evidence}."
    if disagree and not agree:
        return "Not priced", f"{evidence}: bond investors are not trading this story."
    if not agree and not disagree:
        return "Not priced", f"{evidence}: bond investors have not reacted to it."
    return "Partly", f"{evidence}."


def rank_themes(news, past, asof, sc, comps) -> list:
    yh = _yahoo_change(["SMH", "IGV", "GC=F", "^GSPC"], past)
    ranked = []
    for t in THEMES:
        inside, _ = _window_items(news["theme"].get(t["key"], []), past, asof)
        expect = t["expect"]
        if expect == "jobs":
            u = sc["by_key"].get("unrate")
            sign = -1 if u and (u["change"] or 0) > 0 else +1
            expect = {"d2": sign}
        verdict, evidence = _verdict(expect, comps)
        ranked.append({"key": t["key"], "name": t["name"], "channel": t["channel"], "mechanism": t["mechanism"],
                       "volume": len(inside), "life": _life_line(t["key"], sc, yh), "verdict": verdict,
                       "evidence": evidence, "headlines": inside[:3]})
    total = sum(r["volume"] for r in ranked) or 1
    for r in ranked:
        r["share"] = round(r["volume"] / total, 2)
    ranked.sort(key=lambda r: -r["volume"])
    return ranked


def _fomc_phrase(m):
    """Plain-language odds: 'markets see a 70% chance of no change and a 30% chance of a 25bp hike'."""
    hold, hike, cut = m["p_hold"] * 100, m["p_hike"] * 100, m["p_cut"] * 100
    parts = [f"a {hold:.0f}% chance of no change"] if hold >= 1 else []
    if hike >= 1:
        parts.append(f"a {hike:.0f}% chance of a 25bp hike")
    if cut >= 1:
        parts.append(f"a {cut:.0f}% chance of a 25bp cut")
    return "markets see " + " and ".join(parts) + f" (probability-weighted, {m['delta_bp']:+.1f}bp)"


def _fomc_short(m):
    """'FOMC (likely hold: 70%; hike 30%)'."""
    odds = {"hold": m["p_hold"], "hike": m["p_hike"], "cut": m["p_cut"]}
    top = max(odds, key=odds.get)
    rest = "; ".join(f"{k} {v * 100:.0f}%" for k, v in odds.items() if k != top and v >= 0.01)
    return f"FOMC (likely {top}: {odds[top] * 100:.0f}%" + (f"; {rest})" if rest else ")")


# ---------------------------------------------------------------------------
# Shared pieces used by both the near-term and the long-window story
# ---------------------------------------------------------------------------
def watch_list(fed, auctions):
    out = []
    if fed and fed.get("meetings"):
        m = fed["meetings"][0]
        out.append({"when": m["date"], "what": f"FOMC decision: {_fomc_phrase(m)}.", "short": _fomc_short(m)})
    if auctions:
        for u in auctions.get("coupons", [])[:3]:
            size = f"${u['offering_bn']:.0f}bn " if u.get("offering_bn") else ""
            name = u["security"].split(" (")[0]
            out.append({"when": u["auction_date"], "short": f"{name} auction",
                        "what": f"{size}{name} auction" + (f"; it trades {abs(u['now_vs_last_bp']):.0f}bp {'above' if u['now_vs_last_bp'] > 0 else 'below'} the last equivalent auction's yield." if u.get("now_vs_last_bp") is not None else ".")})
    out.sort(key=lambda w: w["when"])
    return out


def data_brief(k):
    bits = []
    if k.get("cpi"):
        bits.append(f"CPI {k['cpi']['now']['value']:.1f}% y/y ({k['cpi']['now']['period']})")
    if k.get("core_pce"):
        bits.append(f"core PCE {k['core_pce']['now']['value']:.1f}% ({k['core_pce']['now']['period']})")
    if k.get("unrate"):
        bits.append(f"unemployment {k['unrate']['now']['value']:.1f}% ({k['unrate']['now']['period']})")
    if k.get("fedfunds"):
        bits.append(f"fed funds {k['fedfunds']['now']['value'] - 0.25:.2f}–{k['fedfunds']['now']['value']:.2f}%")
    return "; ".join(bits) + "." if bits else "No macro data available."
