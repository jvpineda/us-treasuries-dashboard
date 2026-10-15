"""The story engine: every curve move told as a story about the economy.

Bond yields are anchored on what is happening in the economy. So the story always runs in the same order:

  1. The thesis: what the curve did, what that says investors expect, and the economic story behind it.
  2. What happened: the events and data in the economy (local and global) that drove the move.
  3. What the curve says about investors: the shape of the move read as expectations.
  4. Checking the thesis: business and consumer surveys, and investment data, confirm or contradict it.
  5. What would change the story: the risks and the next catalysts.

Windows are told at the scale that fits them:
  - up to 2 years: the current story, from the data and verified news in the window;
  - 2 to 20 years: the episodes in between (COVID, the inflation shock, the AI boom ...), each told as a story;
  - 20 years or more: the secular story (four decades of falling inflation and rates) and the episodes on top of it.
"""
from __future__ import annotations

from datetime import date, timedelta

import sources as S

# ---------------------------------------------------------------------------
# Episodes: dated history, told as cause -> economy -> Fed -> yields.
# Through 2025 from the historical record; 2026 onward is described from the data only (see current_episode).
# ---------------------------------------------------------------------------
EPISODES = [
    {"start": (1979, 10), "end": (1982, 10), "title": "The Volcker shock",
     "story": "After a decade of oil shocks and loose policy, inflation hit 14.8% in March 1980. Paul Volcker's Fed pushed "
              "short-term rates toward 20%, causing back-to-back recessions; the 10Y peaked near 15.8% in September 1981. "
              "Breaking inflation is what started the 40-year bond rally.",
     "channel": "The Fed crushed inflation with record-high rates"},
    {"start": (1990, 7), "end": (1992, 9), "title": "Savings-and-loan bust and the 1990–91 recession",
     "story": "The savings-and-loan crisis choked lending and Iraq's invasion of Kuwait sent oil prices soaring. Spending "
              "slowed into recession and the Fed cut rates from about 8% to 3% by September 1992.",
     "channel": "Recession, then Fed cuts, pulled yields down"},
    {"start": (1994, 2), "end": (1995, 2), "title": "The 1994 bond massacre",
     "story": "With the recovery gathering pace, the Fed doubled rates from 3% to 6% in a year to get ahead of inflation. "
              "Investors were caught off guard and bond prices slumped worldwide.",
     "channel": "A surprise tightening cycle"},
    {"start": (1997, 7), "end": (1998, 12), "title": "Asian crisis, Russia's default and LTCM",
     "story": "Currency crises swept Asia, Russia defaulted and the hedge fund LTCM nearly collapsed. Investors ran to the "
              "safety of Treasuries and the Fed cut three times in late 1998.",
     "channel": "Flight to safety"},
    {"start": (2000, 3), "end": (2003, 6), "title": "Dot-com bust, recession and 9/11",
     "story": "The tech bubble burst and business investment collapsed; the 2001 recession was deepened by the 9/11 "
              "attacks. The Fed cut from 6.5% to 1% and yields fell.",
     "channel": "Investment collapse, then Fed cuts"},
    {"start": (2004, 6), "end": (2006, 6), "title": "Housing boom and the 'conundrum'",
     "story": "As housing boomed, the Fed raised rates 17 times, from 1% to 5.25%. Long-term yields barely rose: savings "
              "from China and oil exporters poured into Treasuries, which Alan Greenspan called a conundrum.",
     "channel": "Fed hikes lifted the short end; global savings held the long end down"},
    {"start": (2007, 8), "end": (2009, 6), "title": "The global financial crisis",
     "story": "Losses on subprime mortgages spread through the banks and Lehman Brothers failed in September 2008. The "
              "economy suffered its worst recession since the 1930s; the Fed cut to zero, began buying bonds (QE), and "
              "investors fled to Treasuries.",
     "channel": "Recession, zero rates and a flight to safety"},
    {"start": (2010, 11), "end": (2014, 10), "title": "Slow recovery, Europe's debt crisis and QE",
     "story": "The recovery was slow and Europe's debt crisis kept investors nervous. The Fed held rates at zero and kept "
              "buying bonds, pinning long-term yields low; the 2013 taper tantrum showed how much yields depended on that support.",
     "channel": "Zero rates and Fed bond buying"},
    {"start": (2015, 12), "end": (2018, 12), "title": "Recovery matures and the Fed normalizes",
     "story": "With unemployment falling toward 4%, the Fed raised rates nine times to 2.5% and began shrinking its bond "
              "holdings in 2017. The 2017 tax cuts boosted growth and the deficit.",
     "channel": "Gradual Fed hikes"},
    {"start": (2019, 1), "end": (2019, 12), "title": "Trade war slowdown",
     "story": "The US-China trade war slowed global growth and factory activity. The Fed made three insurance cuts and "
              "the yield curve briefly inverted.",
     "channel": "Growth scare and Fed cuts"},
    {"start": (2020, 2), "end": (2021, 3), "title": "COVID lockdowns",
     "story": "Lockdowns shut stores, offices and travel. People could not go out, so consumer and business spending "
              "collapsed and unemployment jumped to 14.7% in April 2020. The Fed cut rates to zero and bought bonds without "
              "limit, and yields fell worldwide: the 10Y hit a record low of 0.52% in August 2020.",
     "channel": "Spending collapse, zero rates and QE"},
    {"start": (2021, 4), "end": (2023, 10), "title": "The inflation shock",
     "story": "Reopening demand, stimulus checks and broken supply chains, then Russia's invasion of Ukraine in February "
              "2022, drove CPI inflation to 9.1% in June 2022, a 40-year high. The Fed raised rates 5.25 percentage points "
              "in 16 months, the fastest since the 1980s, and the 10Y climbed to about 5% by October 2023 as deficits added supply.",
     "channel": "Inflation forced the fastest hiking cycle in 40 years"},
    {"start": (2023, 11), "end": (2024, 12), "title": "Disinflation and the first cuts",
     "story": "Inflation cooled toward 3% without a recession. The Fed began cutting in September 2024, 100bp by December, "
              "but long-term yields rose as growth stayed solid and deficits stayed large.",
     "channel": "Fed cuts at the front, sticky long end"},
    {"start": (2025, 1), "end": (2025, 12), "title": "Tariffs, slower hiring and more cuts",
     "story": "Sweeping tariffs in April 2025 jolted markets, Moody's removed the last AAA rating on US debt in May, and "
              "hiring slowed through the year while companies poured money into AI. The Fed cut 75bp from September to "
              "December and stopped shrinking its balance sheet.",
     "channel": "Slower hiring brought Fed cuts"},
]
HISTORY_ENDS = date(2025, 12, 31)

SECULAR = {
    "title": "Four decades of falling inflation and rates, now being tested",
    "story": "For forty years after 1981, inflation and interest rates trended down. Volcker's victory over inflation, "
             "globalization (China's entry into the WTO in 2001 brought a flood of cheap goods), ageing populations saving "
             "more, and central banks that kept inflation near 2% pulled the 10Y from about 15.8% in 1981 to 0.5% in 2020. "
             "Since COVID that trend has been tested: inflation came back, governments borrow far more, supply chains are "
             "moving closer to home, and investment demand, now led by AI, is rising. Each of those pushes the economy's "
             "neutral level of rates up.",
    "channel": "Inflation, savings and the neutral rate",
}

SECULAR_SHORT = ("For forty years after 1981, inflation and interest rates trended down; COVID and the inflation that "
                 "followed broke the pattern.")

# ---------------------------------------------------------------------------
# What the shape of a move says about investors
# ---------------------------------------------------------------------------
EXPECT = {
    "Bear flattener": ("hot", "the market is pricing a Fed that has to lean against a hot economy",
                       "Front end leads because it trades the next few FOMCs; the long end lags because tighter policy now "
                       "caps growth and inflation later. A classic hawkish late-cycle repricing."),
    "Twist flattener": ("hot", "the market is pricing a hawkish Fed that ends up slowing growth",
                        "Front end sells off on the Fed while the long end rallies on the growth hit: the market is "
                        "front-running the slowdown."),
    "Parallel bear shift": ("hot", "the market is repricing the whole rates complex higher",
                            "No segment leads: the expected path and term compensation moved up together."),
    "Bear steepener": ("strong", "the market wants more compensation to own duration",
                       "Long end leads: growth optimism, inflation risk or supply indigestion. Real-yield led points to "
                       "growth or supply; breakeven led points to inflation. Long-end auction tails are the tell."),
    "Bull steepener": ("easing", "the market is pricing cuts",
                       "Front end leads the rally. The good-news version has equities holding (a soft landing, the Fed "
                       "easing because inflation is beaten); the bad-news version has risk cracking (the Fed easing because "
                       "growth is breaking)."),
    "Twist steepener": ("easing", "the market is pricing an easier Fed with more inflation or supply risk further out",
                        "Front end rallies on cuts while the long end sells off: the market doubts the Fed can ease without "
                        "reigniting inflation."),
    "Bull flattener": ("weak", "the market is buying duration on growth fears",
                       "Long end leads the rally: a flight to quality, or a call that growth and inflation stay lower for years."),
    "Parallel bull shift": ("weak", "the market is pricing lower rates across the board", "A level rally with no segment leading."),
    "Little changed": ("flat", "nothing priced in or out", "Yields ended close to where they started."),
}
AI_READ = {
    "hot": "AI angle: the capex boom is the growth impulse the Fed is leaning against. Rates are treating it as "
           "inflationary near term, not yet as a productivity story.",
    "strong": "AI angle: the long end is charging for AI-driven growth and the borrowing that funds it.",
    "easing": "AI angle: if the capex boom were running hot, the front end would not be rallying; the market is betting it "
              "is not enough to keep the Fed tight.",
    "weak": "AI angle: the long end is fading the AI growth story.",
    "flat": "AI angle: no change in how rates price the AI cycle.",
}
MOOD_REP = {"hot": "Bear flattener", "strong": "Bear steepener", "easing": "Bull steepener", "weak": "Bull flattener",
            "flat": "Little changed"}
NOW_PRICING = {"hot": "an economy running hot and a Fed that has to lean against it", "strong": "stronger growth ahead",
               "easing": "a Fed that keeps cutting", "weak": "a slowing economy", "flat": "little change"}
PLAIN = {
    "Bear flattener": "yields rose, most at the short end", "Bear steepener": "yields rose, most at the long end",
    "Bull steepener": "yields fell, most at the short end", "Bull flattener": "yields fell, most at the long end",
    "Twist flattener": "short-term yields rose while long-term yields fell",
    "Twist steepener": "short-term yields fell while long-term yields rose",
    "Parallel bear shift": "yields rose about evenly", "Parallel bull shift": "yields fell about evenly",
    "Little changed": "yields barely moved",
}
RISK = {
    "hot": "Pain trade: a soft core print or an air pocket in AI capex. The front end would rip first and the curve "
           "would bull-steepen.",
    "strong": "Pain trade: weaker growth or calmer supply pulls the long end in first; a strong long-end auction is the tell.",
    "easing": "Pain trade: a hot CPI puts hikes back in play and flattens the curve.",
    "weak": "Pain trade: firmer data or heavy supply re-steepens the curve from the long end.",
    "flat": "Range-bound until the next big print or FOMC.",
}

# ---------------------------------------------------------------------------
# Surveys and investment data used to confirm or deny the thesis
# ---------------------------------------------------------------------------
# key, label, FRED id, transform, unit, side, release lag (days from observation date), meaning
SURVEYS = [
    ("outlook", "Factory managers' 6-month outlook", "GAFDFSA066MSFRBPHI", "level", "index", "business", 20,
     "Philadelphia Fed survey: share expecting better business minus share expecting worse"),
    ("capex_plans", "Companies' plans to invest", "CEFDFSA066MSFRBPHI", "level", "index", "business", 20,
     "Philadelphia Fed survey: share planning more capital spending in six months minus share planning less"),
    ("capex_orders", "Orders for business equipment", "NEWORDER", "yoy", "% y/y", "business", 57,
     "Core capital goods orders (excluding defense and aircraft), year over year"),
    ("it_invest", "Spending on computers, software and data-center gear", "A679RC1Q027SBEA", "yoy", "% y/y", "ai", 120,
     "Private investment in information processing equipment and software (BEA), year over year"),
    ("sentiment", "Consumer sentiment", "UMCSENT", "level", "index", "consumer", 28,
     "University of Michigan survey of households"),
    ("infl_exp", "Consumers' expected inflation, next 12 months", "MICH", "level", "%", "consumer", 28,
     "University of Michigan survey of households"),
]
AVG_FROM = date(2000, 1, 1)


PROPER = ("Fed", "Europe", "China", "Russia", "Iran", "Japan", "Moody", "Volcker", "Lehman", "Alan", "Paul")


def lc(t: str) -> str:
    """Lower-case the first letter unless it starts an acronym ('AI', 'COVID') or a proper noun ('Fed')."""
    if not t or (len(t) > 1 and t[1].isupper()) or t.startswith(PROPER):
        return t
    return t[:1].lower() + t[1:]


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def _yoy(pts, quarterly=False):
    idx = {(d.year, d.month): v for d, v in pts}
    return [(d, (v / idx[(d.year - 1, d.month)] - 1) * 100) for d, v in pts if (d.year - 1, d.month) in idx]


def _known(pts, when, lag):
    best = None
    for d, v in pts:
        if d + timedelta(days=lag) <= when:
            best = (d, v)
    return best


def _period(sid, d):
    return f"Q{(d.month - 1) // 3 + 1} {d.year}" if sid.endswith("Q027SBEA") else f"{d:%b} {d.year}"


def surveys(past: date, asof: date) -> list:
    """Each survey: latest reading, reading known at the window start, and its average since 2000."""
    out = []
    for key, label, sid, kind, unit, side, lag, meaning in SURVEYS:
        pts = _try(S.fred, sid, date(1998, 1, 1)) or []
        if kind == "yoy":
            pts = _yoy(pts)
        if not pts:
            continue
        now = pts[-1]
        then = _known(pts, past, lag)
        hist = [v for d, v in pts if d >= AVG_FROM]
        avg = sum(hist) / len(hist)
        out.append({"key": key, "label": label, "series": sid, "unit": unit, "side": side, "meaning": meaning,
                    "now": round(now[1], 1), "now_period": _period(sid, now[0]),
                    "then": round(then[1], 1) if then else None, "then_period": _period(sid, then[0]) if then else None,
                    "avg": round(avg, 1), "avg_from": AVG_FROM.year, "avg_n": len(hist),
                    "strong": now[1] > avg})
    return out


def _fmt(s, v):
    return f"{v:.1f}%" if s["unit"] in ("% y/y", "%") else f"{v:.1f}"


def survey_verdict(mood: str, sv: list) -> dict:
    """Do business and consumer surveys back the economy the curve is pricing?"""
    by = {s["key"]: s for s in sv}
    biz = [s for s in sv if s["side"] in ("business", "ai")]
    strong = [s for s in biz if s["strong"]]
    n = len(biz)
    cons = by.get("sentiment")
    if not n:
        return {"verdict": "No survey data", "detail": "", "business_strong": 0, "business_n": 0}
    share = len(strong) / n
    if mood in ("hot", "strong"):
        verdict = "Confirmed" if share >= 0.67 else "Partly confirmed" if share >= 0.34 else "Not confirmed"
        detail = (f"{len(strong)} of {n} business measures are running above their average since {AVG_FROM.year}"
                  + (", so businesses are as upbeat as the curve implies." if share >= 0.67 else
                     ", so business confidence only partly matches what the curve implies." if share >= 0.34 else
                     ", so businesses are gloomier than the curve implies."))
    elif mood == "weak":
        verdict = "Confirmed" if share <= 0.33 else "Partly confirmed" if share <= 0.66 else "Not confirmed"
        detail = (f"{len(strong)} of {n} business measures are above their average since {AVG_FROM.year}"
                  + (", consistent with the gloom priced in the curve." if share <= 0.33 else
                     ", so the economy looks sturdier than the curve implies."))
    elif mood == "easing":
        good = share >= 0.5
        verdict = "Optimistic version" if good else "Pessimistic version"
        detail = (f"{len(strong)} of {n} business measures are above their average since {AVG_FROM.year}: "
                  + ("investors are pricing cuts while businesses stay confident, the soft-landing version of the story."
                     if good else "investors are pricing cuts as businesses lose confidence, the weakening-economy version."))
    else:
        verdict = "Neutral"
        detail = f"{len(strong)} of {n} business measures are above their average since {AVG_FROM.year}."
    split = ""
    if cons and biz:
        if share >= 0.5 and not cons["strong"]:
            split = (f" Households feel very differently: consumer sentiment is {_fmt(cons, cons['now'])} ({cons['now_period']}), "
                     f"against an average of {_fmt(cons, cons['avg'])}. Companies are spending; consumers feel squeezed.")
        elif share < 0.5 and cons["strong"]:
            split = f" Consumers are more upbeat than businesses: sentiment {_fmt(cons, cons['now'])} vs an average of {_fmt(cons, cons['avg'])}."
    fresh = [s_ for s_ in biz if s_.get("then") is not None and s_.get("then_period") != s_["now_period"]]
    if fresh:
        better = sum(s_["now"] > s_["then"] for s_ in fresh)
        window = f" In this window {better} of {len(fresh)} business measures that printed improved."
    else:
        window = " No business survey printed inside this window, so it cannot confirm or deny the move itself."
    return {"verdict": verdict, "detail": detail + window + split, "business_strong": len(strong), "business_n": n,
            "consumer_split": bool(split), "fresh": len(fresh)}


# ---------------------------------------------------------------------------
# Episodes and the current (data-described) chapter
# ---------------------------------------------------------------------------
def _d(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def _m(d: date) -> str:
    return f"{d:%b} {d.year}"


def _ep_dates(e):
    (y0, m0), (y1, m1) = e["start"], e["end"]
    return date(y0, m0, 1), date(y1, m1, 28)


def _monthly_at(pts, d):
    best = None
    for t, v in pts:
        if t <= d:
            best = (t, v)
        else:
            break
    return best


def current_episode(asof: date, data: dict, it_yoy=None, moves=None) -> dict | None:
    """The chapter after the documented history ends, described only from the data."""
    start = HISTORY_ENDS + timedelta(days=1)
    if asof <= start + timedelta(days=30):
        return None
    oil = _try(S.fred, "DCOILWTICO", start - timedelta(days=40)) or []
    o0 = _monthly_at(oil, start)
    o1 = oil[-1] if oil else None
    cpi = data.get("cpi_yoy") or []
    c0, c1 = _monthly_at(cpi, start), (cpi[-1] if cpi else None)
    moves = moves or []
    hikes = sum(bp for _, bp in moves if bp > 0)
    cuts = -sum(bp for _, bp in moves if bp < 0)
    parts, story = [], []
    if it_yoy is not None and it_yoy >= 6:
        parts.append("an AI investment boom")
        story.append(f"Companies kept pouring money into AI: spending on computers, software and data-center equipment was "
                     f"up {it_yoy:.0f}% from a year earlier.")
    if o0 and o1 and o1[1] / o0[1] - 1 >= 0.25:
        parts.append("an oil shock")
        story.append(f"Oil jumped from about ${o0[1]:.0f} a barrel ({_m(o0[0])}) to ${o1[1]:.0f} ({_d(o1[0])}), "
                     f"raising fuel and transport costs.")
    elif o0 and o1 and o1[1] / o0[1] - 1 <= -0.25:
        parts.append("an oil slump")
        story.append(f"Oil fell from about ${o0[1]:.0f} a barrel to ${o1[1]:.0f}.")
    if c0 and c1 and c1[1] - c0[1] >= 0.5:
        story.append(f"Inflation turned back up, from {c0[1]:.1f}% ({_m(c0[0])}) to {c1[1]:.1f}% ({_m(c1[0])}).")
    elif c0 and c1 and c1[1] - c0[1] <= -0.5:
        story.append(f"Inflation kept cooling, from {c0[1]:.1f}% to {c1[1]:.1f}%.")
    if hikes and not cuts:
        parts.append("a Fed back to raising rates")
        story.append(f"The Fed reversed course and raised rates {hikes}bp ({', '.join(_m(d) for d, bp in moves if bp > 0)}).")
    elif cuts and not hikes:
        parts.append("more Fed cuts")
        story.append(f"The Fed cut rates a further {cuts}bp.")
    elif hikes and cuts:
        story.append(f"The Fed cut {cuts}bp and then raised rates {hikes}bp.")
    else:
        story.append("The Fed kept rates on hold.")
    title = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0] if parts else "The 2026 economy")
    return {"start": (start.year, start.month), "end": (asof.year, asof.month), "title": title[0].upper() + title[1:],
            "story": " ".join(story), "channel": "Described from the data", "data_only": True}


def episodes_in(past: date, asof: date, data: dict, cur: dict | None) -> list:
    """Documented episodes overlapping the window (at least a month inside it), oldest first, plus the current one."""
    out = []
    for e in EPISODES + ([cur] if cur else []):
        s, en = _ep_dates(e)
        if s <= asof - timedelta(days=30) and en >= past + timedelta(days=30):
            out.append(dict(e, **_ep_moves(e, past, asof, data)))
    return out


def _ep_moves(e, past, asof, data):
    """What the 10Y and 2Y did during the part of the episode inside the window (monthly averages)."""
    s, en = _ep_dates(e)
    s, en = max(s, date(past.year, past.month, 1)), min(en, asof)
    a10, b10 = _monthly_at(data["gs10"], s), _monthly_at(data["gs10"], en)
    a2, b2 = _monthly_at(data["gs2"], s), _monthly_at(data["gs2"], en)
    out = {"from": s.isoformat(), "to": en.isoformat()}
    if a10 and b10:
        out.update(y10_from=round(a10[1], 2), y10_to=round(b10[1], 2), d10=round((b10[1] - a10[1]) * 100))
        inside = [(t, v) for t, v in data["gs10"] if a10[0] <= t <= en]
        if inside:
            lo, hi = min(inside, key=lambda x: x[1]), max(inside, key=lambda x: x[1])
            out.update(lo=round(lo[1], 2), lo_date=lo[0].isoformat(), hi=round(hi[1], 2), hi_date=hi[0].isoformat(),
                       swing=round((hi[1] - lo[1]) * 100))
    if a2 and b2:
        out.update(y2_from=round(a2[1], 2), y2_to=round(b2[1], 2), d2=round((b2[1] - a2[1]) * 100))
    return out


def _ep_line(e):
    if e.get("d10") is None:
        return ""
    f, t = _m(date.fromisoformat(e["from"])), _m(date.fromisoformat(e["to"]))
    if e.get("swing") and e["swing"] >= 2 * max(abs(e["d10"]), 25):
        # A round trip: tell the path, not just the endpoints.
        lo_first = e["lo_date"] < e["hi_date"]
        x1, d1, x2, d2_ = (e["lo"], e["lo_date"], e["hi"], e["hi_date"]) if lo_first else (e["hi"], e["hi_date"], e["lo"], e["lo_date"])
        if (lo_first and x1 < e["y10_from"]) or (not lo_first and x1 > e["y10_from"]):
            return (f"The 10Y {'fell' if lo_first else 'rose'} from {e['y10_from']:.2f}% ({f}) to {x1:.2f}% "
                    f"({_m(date.fromisoformat(d1))}), then {'rebounded' if lo_first else 'fell back'} to {e['y10_to']:.2f}% by {t} (monthly averages).")
    verb = "fell" if e["d10"] < 0 else "rose"
    return f"The 10Y {verb} from {e['y10_from']:.2f}% to {e['y10_to']:.2f}% ({f} to {t} averages)."


# ---------------------------------------------------------------------------
# Near-window story: the drivers in the economy
# ---------------------------------------------------------------------------
def _val(k, key, which="now"):
    r = k.get(key)
    return (r[which]["value"], r[which]["period"]) if r and r.get(which) else (None, None)


def _new(k, key):
    r = k.get(key)
    return bool(r and r.get("then") and r["then"]["period"] != r["now"]["period"])


def near_drivers(k: dict, moves: list, sv: dict, yh: dict, flip: str | None, days: int = 365) -> list:
    """Sentences about the economy in the window, in causal order: business and AI, energy, inflation, jobs, Fed, world."""
    out = []
    it, cap, plans = sv.get("it_invest"), sv.get("capex_orders"), sv.get("capex_plans")
    smh = yh.get("SMH")
    fresh = days >= 80 or any(x and x.get("then_period") and x["then_period"] != x["now_period"] for x in (it, cap))
    if not fresh:
        pass
    elif it and it["now"] >= 6:
        bits = [f"spending on computers, software and data-center equipment was up {it['now']:.0f}% on a year earlier ({it['now_period']})"]
        if cap and cap["now"] >= 5:
            bits.append(f"orders for business equipment were up {cap['now']:.0f}% ({cap['now_period']})")
        tail = f", and chip stocks gained {smh['pct']:.0f}% in the window" if smh and smh["pct"] >= 10 else ""
        out.append(("ai", "Businesses kept investing heavily in AI: " + " and ".join(bits) + tail + "."))
    elif it:
        out.append(("ai", f"Business investment in technology was growing only {it['now']:.0f}% a year ({it['now_period']}), "
                          f"so the AI build-out was not the main force in this window."))
    o0, p0 = _val(k, "oil", "then")
    o1, p1 = _val(k, "oil")
    if o0 and o1 and abs(o1 / o0 - 1) >= 0.15:
        up = o1 > o0
        g1, gp = _val(k, "gas")
        out.append(("energy", f"Oil {'jumped' if up else 'slid'} from ${o0:.0f} to ${o1:.0f} a barrel ({p0} to {p1})"
                              + (f", taking gasoline to ${g1:.2f} a gallon" if g1 and up else "") + "."))
    if _new(k, "cpi"):
        c0, q0 = _val(k, "cpi", "then")
        c1, q1 = _val(k, "cpi")
        core, _ = _val(k, "core_cpi")
        if abs(c1 - c0) >= 0.3:
            narrow = core is not None and c1 > c0 and core <= c1 - 0.5
            out.append(("inflation", f"Inflation {'picked up' if c1 > c0 else 'cooled'}, from {c0:.1f}% ({q0}) to {c1:.1f}% ({q1})"
                                     + (f", while underlying (core) inflation stayed at {core:.1f}%: the jump came from energy, not from prices across the board" if narrow
                                        else f"; underlying (core) inflation was {core:.1f}%" if core else "") + "."))
        else:
            out.append(("inflation", f"Inflation held near {c1:.1f}% ({q1}), still well above the Fed's 2% goal."
                                     if c1 >= 2.8 else f"Inflation held near {c1:.1f}% ({q1})."))
    if _new(k, "unrate"):
        u0, q0 = _val(k, "unrate", "then")
        u1, q1 = _val(k, "unrate")
        if abs(u1 - u0) >= 0.3:
            out.append(("jobs", f"Unemployment {'rose' if u1 > u0 else 'fell'} from {u0:.1f}% to {u1:.1f}% ({q1})."))
    hikes = [(d, bp) for d, bp in moves if bp > 0]
    cuts = [(d, bp) for d, bp in moves if bp < 0]
    if hikes or cuts:
        txt = []
        if cuts:
            txt.append(f"cut rates {-sum(bp for _, bp in cuts)}bp ({', '.join(_m(d) for d, _ in cuts)})")
        if hikes:
            txt.append(f"raised rates {sum(bp for _, bp in hikes)}bp ({', '.join(_m(d) for d, _ in hikes)})")
        out.append(("fed", "The Fed " + " and then ".join(txt) + (f", and markets {flip}." if flip else ".")))
    elif flip and "barely" not in flip:
        out.append(("fed", f"The Fed held rates, but markets {flip}."))
    j0, _ = _val(k, "jgb10", "then")
    j1, jp = _val(k, "jgb10")
    if j0 is not None and j1 is not None and j1 - j0 >= 0.3:
        out.append(("global", f"Abroad, Japan's 10-year yield climbed from {j0:.2f}% to {j1:.2f}% ({jp}), pulling global "
                              f"investors' money toward home markets."))
    return out


def _front_flip(a, k):
    t2 = {t["tenor"]: t for t in a["tenors"]}.get("2Y")
    ff0, ff1 = _val(k, "fedfunds", "then")[0], _val(k, "fedfunds")[0]
    if not t2 or ff0 is None or ff1 is None:
        return None
    g0, g1 = (t2["past"] - (ff0 - 0.125)) * 100, (t2["today"] - (ff1 - 0.125)) * 100
    if g0 < -15 and g1 > 15:
        return "flipped from expecting rate cuts to expecting hikes"
    if g0 > 15 and g1 < -15:
        return "flipped from expecting hikes to expecting cuts"
    if g1 - g0 > 15:
        return "moved to expect a tighter Fed"
    if g1 - g0 < -15:
        return "moved to expect an easier Fed"
    return "barely changed their view of the Fed"


# ---------------------------------------------------------------------------
# The story
# ---------------------------------------------------------------------------
WHEN = {"1D": "Over the past day", "1W": "Over the past week", "1M": "Over the past month",
        "3M": "Over the past three months", "1Y": "Over the past year"}


def build(a: dict, mode: str, sc: dict, data: dict, moves: list, fed: dict | None, watch: list,
          themes: list | None = None, yh: dict | None = None, dc: dict | None = None) -> dict:
    k = sc["by_key"]
    T = {t["tenor"]: t for t in a["tenors"]}
    d2, d10, d30 = (T[x]["chg_bp"] or 0 for x in ("2Y", "10Y", "30Y"))
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    P0, P1 = _d(past), _d(asof)
    when = WHEN.get(a["horizon"], f"Since {P0}")
    regime = a["regime"]
    mood, expect, why_shape = EXPECT.get(regime, EXPECT["Little changed"])
    yh = yh or {}
    sv_list = surveys(past, asof)
    sv = {s["key"]: s for s in sv_list}
    it = sv.get("it_invest")
    cur_moves = _fed_moves_since(HISTORY_ENDS, asof)
    cur = current_episode(asof, data, it["now"] if it else None, cur_moves)
    # Over long windows the net shape is history; the survey check tests what investors price today.
    if mode != "near":
        up, down = sum(bp for _, bp in cur_moves if bp > 0), -sum(bp for _, bp in cur_moves if bp < 0)
        mood = "hot" if up > down else "easing" if down > up else mood
    verdict = survey_verdict(mood, sv_list)
    eps = episodes_in(past, asof, data, cur)
    at = a["attribution"]
    real, be = at.get("real_bp"), at.get("be_bp")
    yrs = (asof - past).days / 365.25

    # ---- What happened (the economy) ----
    flip = _front_flip(a, k) if mode == "near" else None
    if mode == "near":
        drivers = near_drivers(k, moves, sv, yh, flip, (asof - past).days)
        backdrop_ep = cur if cur and past >= HISTORY_ENDS else (eps[-1] if eps else None)
        happened = " ".join(t for _, t in drivers) or "No major data release changed in this window."
        top = [t for t in (themes or []) if t.get("volume")][:2]
        if a["horizon"] in ("1D", "1W") or not drivers:
            catalyst = ((f"In the news, coverage tying the move to rates centred on {lc(top[0]['name'])} ({top[0]['volume']} verified stories)"
                         + (f", then {lc(top[1]['name'])} ({top[1]['volume']})" if len(top) > 1 else "") + ".") if top else "")
            happened = (f"This window sits inside the bigger story of {lc(backdrop_ep['title'])}. " if backdrop_ep else "") + \
                       (catalyst + " " if catalyst else "") + (happened if drivers else "No major economic data changed in the window.")
            drivers = ([("news", catalyst)] if catalyst else []) + drivers
        story_name = backdrop_ep["title"] if backdrop_ep else "The economy"
    else:
        drivers = []
        n_sent = 3 if len(eps) <= 6 else 1
        happened = " ".join(f"{e['title']} ({_m(date.fromisoformat(e['from']))}–{_m(date.fromisoformat(e['to']))}): "
                            f"{_short(e['story'], n_sent)}" for e in eps) or "No documented episode in this window."
        biggest = max(eps, key=lambda e: max(abs(e.get("d10") or 0), e.get("swing") or 0)) if eps else None
        story_name = biggest["title"] if biggest else "The cycle"

    # ---- The long view ----
    if mode == "secular":
        long_view = SECULAR["story"]
    elif mode == "cyclical":
        long_view = (SECULAR_SHORT + " Under 20 years, though, the trend is set by a handful of episodes, each a shock to "
                     "the economy that the Fed and investors responded to. " + _backdrop(past, data))
    else:
        prior = [e for e in EPISODES if _ep_dates(e)[1] < past][-2:]
        long_view = (SECULAR_SHORT + " How we got here: " + "; ".join(f"{e['title'].lower()} ({_m(_ep_dates(e)[0])}–{_m(_ep_dates(e)[1])})" for e in prior)
                     + (f"; then, since January 2026, {lc(cur['title'])}" if cur and past > HISTORY_ENDS - timedelta(days=400) else "")
                     + ". " + (cur["story"] if cur and past >= HISTORY_ENDS else ""))

    # ---- What the curve says ----
    level = (d2 + d10 + d30) / 3
    if mode != "near":
        rep = MOOD_REP.get(mood, "Little changed")
        _, expect_now, why_now = EXPECT[rep]
    else:
        expect_now, why_now = expect, why_shape
    shape = (f"{when}, {PLAIN.get(regime, 'yields moved')} (a {regime.lower()}): {expect}." if regime != "Little changed"
             else f"{when}, yields barely moved: {expect}.")
    split = ""
    if real is not None and be is not None and abs(d10) >= 8:
        if abs(real) >= 2 * abs(be):
            split = (f" Almost all of the 10Y's move came from real yields, which track growth and the Fed, rather than from "
                     f"inflation expectations: investors are pricing {'a stronger economy and tighter policy' if real > 0 else 'a weaker economy and easier policy'}, "
                     f"{'not runaway inflation' if real > 0 else 'not a collapse in inflation'}.")
        elif abs(be) >= 2 * abs(real):
            split = (f" Most of the 10Y's move came from inflation expectations rather than real yields: investors are "
                     f"{'worried about inflation' if be > 0 else 'less worried about inflation'}.")
        else:
            split = " The 10Y's move was split between growth and the Fed (real yields) and inflation expectations."
    ai_on = mode == "near" or asof.year >= 2024 and any("AI" in e["title"] for e in eps)
    ai_read = (" " + AI_READ[mood]) if (mode == "near" or ai_on) else ""
    if mode == "near":
        curve_says = shape + " " + why_shape + split + ai_read
    else:
        latest = eps[-1] if eps else None
        curve_says = (f"Net, {PLAIN.get(regime, 'yields moved')} over {yrs:.0f} years (a {regime.lower()}). Over a window this long "
                      f"the net shape adds up several chapters; it is history, not a forecast."
                      + (f" What investors price today comes from the latest chapter, {lc(latest['title'])}: {expect_now}. {why_now}" if latest else "")
                      + ai_read)

    # ---- The thesis ----
    sv_short = _survey_short(verdict, sv)
    if mode == "near":
        thesis = (f"{when}, {PLAIN.get(regime, 'yields moved')}: {expect}. "
                  f"The story behind it is {lc(story_name)}. "
                  f"{_survey_words(verdict)}")
    else:
        net = f"the 10Y went from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}%"
        chapters = " → ".join(lc(e["title"]) for e in key_chapters(eps)) if eps else ""
        latest = eps[-1] if eps else None
        thesis = (f"{when}, {net}. "
                  + ("Behind it sits the secular story: four decades of falling inflation and rates, now being tested. " if mode == "secular" else "")
                  + (f"The path ran through {chapters}. " if chapters else "")
                  + (f"Today's chapter is {lc(latest['title'])}: investors are pricing {NOW_PRICING[mood]}. "
                     f"{_survey_words(verdict)}" if latest else ""))
    headline = thesis

    # ---- Risks and what to watch ----
    risks = [RISK.get(mood, RISK["flat"])]
    if verdict.get("consumer_split"):
        risks.append("Consumer sentiment is near recession levels. If it shows up in spending, growth rolls over faster "
                     "than the curve prices and the long end rallies.")
    if sv.get("it_invest") and sv["it_invest"]["now"] >= 6:
        risks.append("Business investment is an AI trade. Capex guidance cuts from the largest spenders would pull the "
                     "growth leg out from under the curve.")
    if dc and dc.get("signals_on", 0) >= 3:
        risks.append(f"Government debt is in the late stage of Ray Dalio's long-term debt cycle ({dc['signals_on']} of "
                     f"{dc['signals_total']} warning signs on). If buyers step back, long-term yields can jump.")
    nxt = " · ".join(f"{date.fromisoformat(w['when']):%b} {date.fromisoformat(w['when']).day} {w['short']}" for w in watch[:4])

    # ---- Executive summary (same five labels every window) ----
    brief = [
        {"label": "What happened", "text": _brief_happened(drivers, happened, mode, eps, k, moves, sv)},
        {"label": "What the curve is pricing", "text": (f"{expect[0].upper() + expect[1:]}. {_first_sentence(why_shape)}" if mode == "near" else
                                                    f"Today, {expect_now}. The net shape over {yrs:.0f} years ({regime.lower()}) is history, not a forecast.")},
        {"label": "Do surveys agree?", "text": f"{verdict['verdict']}. {verdict['detail']}"},
        {"label": "The long view", "text": _short(long_view, 2)},
        {"label": "What would change it", "text": risks[0] + (f" Next: {nxt}." if nxt else "")},
    ]

    # ---- Full story (same five chapters every window) ----
    summary = [
        {"label": "The long view", "metric": SECULAR["title"] if mode == "secular" else ("Episodes in the window" if mode == "cyclical" else "How we got here"),
         "text": long_view},
        {"label": "What happened", "metric": story_name, "text": happened},
        {"label": "What the curve says", "metric": regime, "text": curve_says},
        {"label": "Checking the thesis", "metric": f"Surveys: {verdict['verdict'].lower()}",
         "text": verdict["detail"] + " " + _survey_sentences(sv_list)},
        {"label": "What would change the story", "metric": f"Next: {_d(date.fromisoformat(watch[0]['when']))}" if watch else "",
         "text": " ".join(risks) + (" Coming up: " + "; ".join(f"{_d(date.fromisoformat(w['when']))}, {w['what'].rstrip('.')}" for w in watch[:3]) + "." if watch else "")},
    ]

    # ---- Key numbers (kept short) ----
    deck = [f"{P0} to {P1}: 2Y {d2:+.0f}bp, 10Y {d10:+.0f}bp, 30Y {d30:+.0f}bp ({regime.lower()}).",
            (f"10Y: real yield {real:+.0f}bp (growth and the Fed), inflation expectations {be:+.0f}bp." if real is not None else
             "10Y split into real yield and inflation expectations: not available for this window."),
            f"Surveys: {verdict['business_strong']} of {verdict['business_n']} business measures above their {AVG_FROM.year}+ average."]

    # ---- Three story cards ----
    if mode == "near":
        cards = _theme_cards(themes or [], a)
    else:
        cards = _episode_cards(eps, mode)

    return {"headline": headline, "thesis_line": thesis, "brief": brief, "summary": summary, "deck": deck, "risks": risks,
            "themes": cards, "all_themes": [{x: t[x] for x in ("key", "name", "volume", "share", "verdict")} for t in (themes or [])],
            "watch": watch, "lead": story_name, "story_name": story_name, "mood": mood,
            "window": {"from": P0, "to": P1}, "thesis": [x["label"] + ": " + x["text"] for x in summary[1:4]],
            "surveys": sv_list, "survey_verdict": verdict, "episodes": eps, "timeline": _timeline(eps, moves, past, asof, themes),
            "surprises": []}


SHORT_ORDER = ["news", "ai", "energy", "inflation", "fed", "jobs", "global"]


def _clause(key, text, k, moves, sv):
    """A compact version of each driver for the executive summary."""
    if key == "ai":
        it, cap = sv.get("it_invest"), sv.get("capex_orders")
        if it and it["now"] >= 6:
            return (f"an AI spending boom (tech investment +{it['now']:.0f}% y/y"
                    + (f", equipment orders +{cap['now']:.0f}%" if cap and cap["now"] >= 5 else "") + ")")
        return None
    if key == "energy":
        o0, o1 = _val(k, "oil", "then")[0], _val(k, "oil")[0]
        return f"oil {'up' if o1 > o0 else 'down'} from ${o0:.0f} to ${o1:.0f} a barrel"
    if key == "inflation":
        c0, c1, core = _val(k, "cpi", "then")[0], _val(k, "cpi")[0], _val(k, "core_cpi")[0]
        if abs(c1 - c0) < 0.3:
            return f"inflation steady near {c1:.1f}%"
        narrow = core is not None and c1 > c0 and core <= c1 - 0.5
        return f"inflation {c0:.1f}% → {c1:.1f}%" + (f", driven by energy (core {core:.1f}%)" if narrow else "")
    if key == "fed":
        cuts, hikes = -sum(bp for _, bp in moves if bp < 0), sum(bp for _, bp in moves if bp > 0)
        last_hike = max((d for d, bp in moves if bp > 0), default=None)
        parts = ([f"cut {cuts}bp"] if cuts else []) + ([f"hiked {hikes}bp" + (f" ({_m(last_hike)})" if last_hike else "")] if hikes else [])
        flip = text.split("markets ")[-1].rstrip(".") if "markets " in text else ""
        return ("the Fed " + ", then ".join(parts) if parts else "the Fed on hold") + (f"; markets {flip}" if flip else "")
    if key == "jobs":
        return text.rstrip(".").replace("Unemployment", "unemployment")
    if key == "global":
        j0, j1 = _val(k, "jgb10", "then")[0], _val(k, "jgb10")[0]
        return f"Japan's 10Y yield {j0:.2f}% → {j1:.2f}%"
    return text


def _brief_happened(drivers, happened, mode, eps, k=None, moves=None, sv=None):
    if mode != "near":
        return "; ".join(f"{e['title']} ({_m(date.fromisoformat(e['from']))}–{_m(date.fromisoformat(e['to']))})" for e in key_chapters(eps)) + "." if eps else happened
    if not drivers:
        return _short(happened, 2)
    by = dict(drivers)
    lead = by.get("news", "")
    clauses = [c for c in (_clause(key, by[key], k, moves or [], sv or {}) for key in SHORT_ORDER if key in by and key != "news") if c]
    body = "; ".join(clauses[:5])
    body = (body[0].upper() + body[1:] + ".") if body else ""
    return (lead + " " + body).strip()


def key_chapters(eps, n=5):
    """All chapters when there are few; otherwise the biggest movers of the 10Y plus the latest, in order."""
    if len(eps) <= n:
        return eps
    big = sorted(eps[:-1], key=lambda e: -max(abs(e.get("d10") or 0), e.get("swing") or 0))[:n - 1]
    return sorted(big, key=lambda e: e["from"]) + [eps[-1]]


def _fed_moves_since(start: date, asof: date):
    pts = _try(S.fred, "DFEDTARU", start - timedelta(days=10)) or []
    out, prev = [], None
    for d, v in pts:
        if prev is not None and v != prev and start < d <= asof:
            out.append((d, round((v - prev) * 100)))
        prev = v
    return out


def _first_sentence(t):
    i = t.find(". ")
    return t if i < 0 else t[:i + 1]


def _short(t, n):
    out, rest = [], t
    for _ in range(n):
        i = rest.find(". ")
        if i < 0:
            out.append(rest)
            rest = ""
            break
        out.append(rest[:i + 1])
        rest = rest[i + 2:]
    return " ".join(x for x in out if x).strip()


def _backdrop(past, data):
    for e in reversed(EPISODES):
        s, en = _ep_dates(e)
        if en < past:
            return f"Just before it began: {e['title'].lower()}."
    return ""


def _survey_words(v):
    """The survey check in words for the headline."""
    vd, split = v["verdict"], v.get("consumer_split")
    if vd == "Confirmed":
        return "Business surveys confirm it" + (": companies are upbeat and investing, but consumers are gloomy." if split else ".")
    if vd == "Partly confirmed":
        return "Business surveys only partly back it."
    if vd == "Not confirmed":
        return "Business surveys do not back it: companies are gloomier than the curve implies."
    if vd == "Optimistic version":
        return "Business surveys point to the optimistic version: cuts with growth holding up."
    if vd == "Pessimistic version":
        return "Business surveys point to the pessimistic version: cuts because growth is weakening."
    return ""


def _survey_short(verdict, sv):
    o, c, s = sv.get("outlook"), sv.get("capex_plans"), sv.get("sentiment")
    bits = []
    if o:
        bits.append(f"factory outlook {o['now']:.0f} vs a {o['avg']:.0f} average")
    if c:
        bits.append(f"capex plans {c['now']:.0f} vs {c['avg']:.0f}")
    if s:
        bits.append(f"consumer sentiment {s['now']:.0f} vs {s['avg']:.0f}")
    return "; ".join(bits)


def _survey_sentences(sv_list):
    out = []
    for s in sv_list:
        rel = "above" if s["strong"] else "below"
        out.append(f"{s['label']}: {_fmt(s, s['now'])} ({s['now_period']}), {rel} its {s['avg_from']}+ average of {_fmt(s, s['avg'])}.")
    return " ".join(out)


def _theme_cards(themes, a):
    """Near windows: the AI story always, plus the two most-covered other themes."""
    ai = next((t for t in themes if t["key"] == "ai_capex"), None)
    rest = [t for t in themes if t["key"] != "ai_capex"][:2]
    cards = ([ai] if ai else []) + rest
    return cards[:3]


def _episode_cards(eps, mode):
    ranked = sorted(eps, key=lambda e: -max(abs(e.get("d10") or 0), e.get("swing") or 0))
    picks = ranked[:2] if mode == "secular" else ranked[:3]
    picks = sorted(picks, key=lambda e: e["from"])
    cards = []
    if mode == "secular":
        cards.append({"key": "secular", "name": SECULAR["title"], "channel": SECULAR["channel"], "mechanism": SECULAR["story"],
                      "volume": None, "life": "", "verdict": "The secular story", "evidence": "", "headlines": [],
                      "links": [{"title": "New York Fed: the natural rate of interest", "url": "https://www.newyorkfed.org/research/policy/rstar"}]})
    for e in picks:
        d10, d2 = e.get("d10"), e.get("d2")
        ev = _ep_line(e)
        if d2 is not None and d10 is not None:
            ev += f" The 2Y {'fell' if d2 < 0 else 'rose'} from {e['y2_from']:.2f}% to {e['y2_to']:.2f}%."
        cards.append({"key": e["title"], "name": f"{e['title']} ({_m(date.fromisoformat(e['from']))}–{_m(date.fromisoformat(e['to']))})",
                      "channel": e["channel"], "mechanism": e["story"], "volume": None, "life": "",
                      "verdict": (("Yields fell, then rebounded" if e["lo_date"] < e["hi_date"] else "Yields rose, then fell back")
                                  if e.get("swing") and e["swing"] >= 2 * max(abs(d10 or 0), 25) else
                                  "Pulled yields down" if (d10 or 0) <= -25 else "Pushed yields up" if (d10 or 0) >= 25 else "Little net effect"),
                      "evidence": ev, "headlines": [], "links": []})
    return cards[:3]


def _timeline(eps, moves, past, asof, themes):
    """Dated events in the window: episodes, Fed decisions and, for short windows, the first verified headline per theme."""
    ev = []
    for e in eps:
        ev.append({"date": e["from"], "kind": "episode", "text": e["title"] + (": described from the data" if e.get("data_only") else "")})
    if (asof - past).days <= 730:
        for d, bp in moves:
            ev.append({"date": d.isoformat(), "kind": "fed", "text": f"Fed {'raises' if bp > 0 else 'cuts'} rates {abs(bp)}bp"})
    else:
        cyc = []
        for d, bp in moves:
            if cyc and (cyc[-1][0] > 0) == (bp > 0):
                cyc[-1][0] += bp; cyc[-1][2] = d; cyc[-1][3] += 1
            else:
                cyc.append([bp, d, d, 1])
        for bp, d0, d1, n in cyc:
            ev.append({"date": d0.isoformat(), "kind": "fed",
                       "text": f"Fed {'raises' if bp > 0 else 'cuts'} rates {abs(bp)}bp" + (f" in {n} moves to {_m(d1)}" if n > 1 else "")})
    for t in (themes or [])[:3]:
        for h in (t.get("headlines") or [])[:1]:
            ev.append({"date": h["date"], "kind": "news", "text": h["title"], "url": h.get("url"), "source": h.get("source"),
                       "theme": t["name"]})
    ev = [x for x in ev if x["date"] and past.isoformat()[:7] <= x["date"][:10] <= asof.isoformat()] if ev else []
    return sorted(ev, key=lambda x: x["date"])


def episode_label(a: date, b: date) -> str | None:
    """The documented episodes that explain a leg from a to b: the one or two with the most overlap, in date order."""
    hits = []
    for e in EPISODES:
        s_, e_ = _ep_dates(e)
        overlap = (min(e_, b) - max(s_, a)).days
        if overlap >= 25:
            hits.append((overlap, s_, e))
    if not hits:
        return None
    hits.sort(key=lambda x: -x[0])
    keep = [hits[0]] + [h for h in hits[1:2] if h[0] >= 270]
    keep.sort(key=lambda x: x[1])
    if len(keep) == 1:
        e = keep[0][2]
        return f"{e['title']}: {lc(e['channel'])}"
    return " → ".join(h[2]["title"] for h in keep)
