"""Secular and cyclical interpretation for windows longer than two years.

A point-to-point comparison over decades hides the path. This module explains long windows the way a macro investor
would:

1. Secular anchor (Fisher / expectations-hypothesis decomposition):
       10Y yield = neutral real rate (r*) + expected inflation + term premium (and residual)
   r* from the New York Fed's Laubach-Williams model; expected inflation from the Cleveland Fed's 10-year
   expectation model; term premium from the Fed Board's Kim-Wright model.
2. Cycles in between: the monthly 10Y path is split into legs at turning points (zigzag), each leg annotated with
   the Fed cycle, inflation, recessions, the monetary-policy regime and the dated history of that period.
3. Ray Dalio's long-term debt cycle (Big Debt Crises; How Countries Go Broke): debt and debt-service indicators,
   the monetary-policy regime (MP1 rates, MP2 QE, MP3 fiscal-monetary coordination) and the "classic template"
   warning signals for government bond markets, with an explicit stage call.

Free data only: FRED, the New York Fed, Yahoo Finance.
"""
from __future__ import annotations

import re
import zipfile
import io
from datetime import date, timedelta

import narrative as N
import sources as S

NEAR_MAX_YEARS = 2     # up to here: the near-term story
CYCLICAL_MAX_YEARS = 20  # 2-20 years: told through the episodes in between; 20 years or more: the secular story


def mode_for(past: date, asof: date) -> str:
    yrs = (asof - past).days / 365.25
    return "near" if yrs <= NEAR_MAX_YEARS else "cyclical" if yrs <= CYCLICAL_MAX_YEARS else "secular"


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def _d(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def _m(d: date) -> str:
    return f"{d:%b} {d.year}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fred(series: str, start=date(1950, 1, 1)):
    return _try(S.fred, series, start) or []


def monthly_mean(pts):
    acc = {}
    for d, v in pts:
        acc.setdefault((d.year, d.month), []).append(v)
    return [(date(y, m, 1), sum(vs) / len(vs)) for (y, m), vs in sorted(acc.items())]


def yoy(pts, lag=12):
    idx = {(d.year, d.month): v for d, v in pts}
    out = []
    for d, v in pts:
        y, m = d.year - (lag // 12), d.month
        p = idx.get((y, m))
        if p:
            out.append((d, (v / p - 1) * 100))
    return out


def rstar():
    """Laubach-Williams one-sided r* estimates, quarterly: [(date, %)]."""
    def fetch():
        raw = S.http_get("https://www.newyorkfed.org/medialibrary/media/research/economists/williams/data/"
                         "Laubach_Williams_current_estimates.xlsx", timeout=40)
        z = zipfile.ZipFile(io.BytesIO(raw))
        x = z.read("xl/worksheets/sheet2.xml").decode()
        out = []
        for row in re.findall(r"<row[^>]*>(.*?)</row>", x, re.S):
            cells = {c: v for c, attrs, v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>[^<]*</f>)?<v>([^<]*)</v>', row)
                     if 't="s"' not in attrs}
            a, c = cells.get("A"), cells.get("C")
            try:
                serial, val = float(a), float(c)
            except (TypeError, ValueError):
                continue
            if 10000 < serial < 80000:
                out.append((date(1899, 12, 30) + timedelta(days=int(serial)), val))
        return out
    return S.cached("rstar", 24 * 3600, lambda: _try(fetch) or [])


def at(pts, d: date):
    """Latest value on or before d."""
    best = None
    for t, v in pts:
        if t <= d:
            best = (t, v)
        else:
            break
    return best


def last(pts):
    return pts[-1] if pts else None


# ---------------------------------------------------------------------------
# Path, cycles and regimes
# ---------------------------------------------------------------------------
# Dated history through 2025 (well documented). Later periods are described from the data only.
ERAS = [
    ((1979, 10), (1982, 10), "Volcker disinflation: fed funds near 20%, 10Y peaks near 15.8% (Sep 1981)"),
    ((1990, 7), (1991, 3), "1990–91 recession"),
    ((1994, 2), (1995, 2), "1994 bond rout: the Fed doubles rates to 6%"),
    ((1997, 7), (1998, 10), "Asian crisis, Russia default and LTCM"),
    ((2000, 3), (2002, 10), "Dot-com bust, 2001 recession and 9/11"),
    ((2001, 1), (2003, 6), "Fed cuts from 6.5% to 1%"),
    ((2004, 6), (2006, 6), "Fed hikes 1% → 5.25%; Greenspan's 'conundrum' as global savings keep long yields low"),
    ((2007, 8), (2009, 6), "Global financial crisis; fed funds to zero (Dec 2008); QE1 begins"),
    ((2010, 11), (2014, 10), "QE2, Operation Twist and QE3; taper tantrum (May–Sep 2013)"),
    ((2011, 8), (2011, 8), "S&P downgrades the US to AA+"),
    ((2015, 12), (2018, 12), "Liftoff and nine hikes to 2.50%; QT1 from Oct 2017"),
    ((2019, 7), (2019, 10), "Three 'insurance' cuts"),
    ((2020, 3), (2021, 12), "COVID: rates to zero, unlimited QE and record deficits; 10Y record low 0.52% (Aug 2020)"),
    ((2022, 3), (2023, 7), "Inflation shock: 525bp of hikes and QT2; 10Y near 5% (Oct 2023)"),
    ((2023, 8), (2023, 8), "Fitch downgrades the US to AA+"),
    ((2024, 9), (2024, 12), "Fed cuts 100bp"),
    ((2025, 5), (2025, 5), "Moody's downgrades the US to Aa1"),
    ((2025, 9), (2025, 12), "Fed cuts 75bp; QT ends (Dec 2025)"),
]


def eras_between(a: date, b: date):
    """History overlapping [a, b], most representative first: overlap length weighted toward the end of the period
    (a falling leg is explained by the crisis that ends it, a rising leg by the shock that drives it)."""
    span = max((b - a).days, 1)
    scored = []
    for (y0, m0), (y1, m1), txt in ERAS:
        s_, e_ = date(y0, m0, 1), date(y1, m1, 28)
        if not (s_ <= b - timedelta(days=30) and e_ >= a + timedelta(days=30)):  # overlap of at least a month
            continue
        o0, o1 = max(s_, a), min(e_, b)
        overlap = max((o1 - o0).days, 0)
        mid = o0 + (o1 - o0) / 2
        weight = 1 + (mid - a).days / span
        scored.append((overlap * weight if (e_ - s_).days >= 80 else overlap * 0.1, txt))
    return [t for _, t in sorted(scored, key=lambda x: -x[0])]


def zigzag(pts, threshold_pct):
    """Turning points of a monthly series where the move since the last pivot reverses by >= threshold."""
    if len(pts) < 3:
        return [pts[0], pts[-1]] if pts else []
    pivots = [pts[0]]
    trend, ext = 0, pts[0]
    for d, v in pts[1:]:
        if trend >= 0 and v >= ext[1]:
            ext = (d, v)
            if trend == 0 and v - pivots[-1][1] >= threshold_pct:
                trend = 1
        elif trend <= 0 and v <= ext[1]:
            ext = (d, v)
            if trend == 0 and pivots[-1][1] - v >= threshold_pct:
                trend = -1
        if trend == 1 and ext[1] - v >= threshold_pct:
            pivots.append(ext); trend, ext = -1, (d, v)
        elif trend == -1 and v - ext[1] >= threshold_pct:
            pivots.append(ext); trend, ext = 1, (d, v)
        elif trend == 0 and abs(v - pivots[-1][1]) < threshold_pct:
            ext = (d, v)
    if pivots[-1][0] != pts[-1][0]:
        pivots.append(pts[-1])
    return pivots


def mp_regime(d: date, ff, walcl_yoy, deficit):
    """Dalio's monetary-policy regimes, read from data: MP1 rates; MP2 QE at the zero bound; MP3 QE plus big deficits."""
    f = at(ff, d)
    w = at(walcl_yoy, d)
    df = at(deficit, d)
    zlb = f and f[1] <= 0.25
    qe = w and w[1] >= 10
    if zlb and qe and df and df[1] <= -10:
        return "MP3"
    if zlb or qe:
        return "MP2"
    return "MP1"


MP_TEXT = {"MP1": "MP1: interest rates are the main tool",
           "MP2": "MP2: rates near zero, the Fed buys bonds (QE)",
           "MP3": "MP3: QE financing large fiscal deficits (fiscal-monetary coordination)"}


def load():
    """All long-history series, cached for a day."""
    def build():
        d = {}
        d["gs10"] = fred("GS10"); d["gs2"] = fred("GS2"); d["gs30"] = fred("GS30"); d["tb3"] = fred("TB3MS")
        d["ff"] = fred("FEDFUNDS"); d["rec"] = fred("USREC", date(1950, 1, 1))
        d["einf"] = fred("EXPINF10YR"); d["cpi_yoy"] = yoy(fred("CPIAUCSL"))
        d["tp"] = monthly_mean(fred("THREEFYTP10", date(1990, 1, 1)))
        d["rstar"] = rstar()
        d["debt_gdp"] = fred("FYGFGDQ188S"); d["int_gdp"] = fred("FYOIGDA188S"); d["deficit"] = fred("FYFSGDA188S")
        intr, rcpt = fred("A091RC1Q027SBEA"), dict(fred("W006RC1Q027SBEA"))
        d["int_rev"] = [(t, v / rcpt[t] * 100) for t, v in intr if rcpt.get(t)]
        gdp = fred("GDP")
        d["ngdp_yoy"] = [(t, (v / dict(gdp)[date(t.year - 1, t.month, 1)] - 1) * 100) for t, v in gdp if date(t.year - 1, t.month, 1) in dict(gdp)]
        treast, debt = monthly_mean(fred("TREAST", date(2002, 1, 1))), fred("FYGFDPUN")
        d["fed_share"] = [(t, v / at(debt, t)[1] * 100) for t, v in treast if at(debt, t)]
        d["foreign_share"] = [(t, v * 1000 / at(debt, t)[1] * 100) for t, v in fred("FDHBFIN") if at(debt, t)]
        walcl = monthly_mean(fred("WALCL", date(2002, 1, 1)))
        d["walcl_yoy"] = yoy(walcl)
        d["dollar"] = monthly_mean(fred("DTWEXBGS", date(2006, 1, 1)))
        d["real10"] = monthly_mean(fred("DFII10", date(2003, 1, 1)))
        g = _try(S.yahoo_chart, "GC=F", "max")
        d["gold"] = monthly_mean(g["hist"]) if g else []
        return d
    return S.cached("secular_data", 24 * 3600, build)


def path(past: date, asof: date, data=None):
    """Monthly path of the 10Y, 2Y, fed funds and the neutral-rate anchor, with recession and MP-regime bands."""
    data = data or load()
    start = date(past.year, past.month, 1)
    rows = []
    for t, v in data["gs10"]:
        if t < start:
            continue
        rs, ei, tp = at(data["rstar"], t), at(data["einf"], t), at(data["tp"], t)
        rows.append({"d": t.isoformat(), "y10": v, "y2": (at(data["gs2"], t) or (None, None))[1],
                     "ff": (at(data["ff"], t) or (None, None))[1],
                     "anchor": round(rs[1] + ei[1], 2) if rs and ei else None,
                     "rec": bool((at(data["rec"], t) or (None, 0))[1]),
                     "mp": mp_regime(t, data["ff"], data["walcl_yoy"], data["deficit"])})
    return rows


def _data_label(a: date, b: date, data) -> str:
    """Describe a period from the data alone (used where the dated history list does not reach)."""
    parts = []
    cyc = fed_cycles(a - timedelta(days=1), b + timedelta(days=27))
    if cyc:
        parts.append("the Fed " + " then ".join(f"{'hiked' if k == 'hike' else 'cut'} {bp}bp" for k, bp, _, _ in cyc))
    c0, c1 = at(data["cpi_yoy"], a), at(data["cpi_yoy"], b)
    if c0 and c1 and abs(c1[1] - c0[1]) >= 0.5:
        parts.append(f"CPI inflation {c0[1]:.1f}% → {c1[1]:.1f}%")
    return ("From the data: " + ", ".join(parts)) if parts else "No change in Fed policy or inflation trend"


def _leg_label(a: date, b: date, data) -> str:
    """Documented history for the part of a leg before 2026; the data describes the rest."""
    end = N.HISTORY_ENDS
    if b <= end + timedelta(days=60):
        return N.episode_label(a, b) or _data_label(a, b, data)
    if a >= end - timedelta(days=30):
        return _data_label(a, b, data)
    lab = N.episode_label(a, end)
    rest = _data_label(max(a, end), b, data).replace("From the data: ", "")
    return f"{lab}; then in 2026, from the data: {rest}" if lab else _data_label(a, b, data)


def legs(past: date, asof: date, mode: str, data=None):
    data = data or load()
    start = date(past.year, past.month, 1)
    pts = [(t, v) for t, v in data["gs10"] if t >= start]
    thr = 1.5 if mode == "secular" else 0.75
    piv = zigzag(pts, thr)
    out = []
    for (a, va), (b, vb) in zip(piv, piv[1:]):
        ffa, ffb = at(data["ff"], a), at(data["ff"], b)
        ca, cb = at(data["cpi_yoy"], a), at(data["cpi_yoy"], b)
        rec_months = sum(1 for t, v in data["rec"] if a <= t <= b and v)
        mps = sorted({mp_regime(t, data["ff"], data["walcl_yoy"], data["deficit"]) for t, _ in pts if a <= t <= b})
        hist = [_leg_label(a, b, data)]
        out.append({"from": a.isoformat(), "to": b.isoformat(), "y_from": round(va, 2), "y_to": round(vb, 2),
                    "chg_bp": round((vb - va) * 100), "months": (b.year - a.year) * 12 + b.month - a.month,
                    "ff_from": ffa and round(ffa[1], 2), "ff_to": ffb and round(ffb[1], 2),
                    "cpi_from": ca and round(ca[1], 1), "cpi_to": cb and round(cb[1], 1),
                    "recession_months": rec_months, "mp": mps, "history": hist})
    return out


def decomposition(past: date, asof: date, data=None):
    """10Y = r* + expected inflation + term premium + residual, at the start and the end of the window."""
    data = data or load()
    def snap(t):
        y = at(data["gs10"], t)
        if not y:
            return None
        m = y[0]  # every component read for the same month as the 10Y average
        r = at(data["rstar"], m); e = at(data["einf"], m); tp = at(data["tp"], m)
        out = {"date": y[0].isoformat(), "y10": round(y[1], 2), "rstar": r and round(r[1], 2), "rstar_date": r and r[0].isoformat(),
               "einf": e and round(e[1], 2), "tp": tp and round(tp[1], 2)}
        if r and e:
            out["anchor"] = round(r[1] + e[1], 2)
            out["residual"] = round(y[1] - r[1] - e[1] - (tp[1] if tp else 0), 2)
        return out
    a, b = snap(date(past.year, past.month, 1)), snap(asof)
    chg = {}
    if a and b:
        for k in ("y10", "rstar", "einf", "tp", "residual", "anchor"):
            if a.get(k) is not None and b.get(k) is not None:
                chg[k] = round((b[k] - a[k]) * 100)
    return {"start": a, "end": b, "chg_bp": chg}


# ---------------------------------------------------------------------------
# Dalio: the long-term debt cycle
# ---------------------------------------------------------------------------
def _avg(pts, a: date, b: date):
    xs = [v for t, v in pts if a <= t <= b]
    return sum(xs) / len(xs) if xs else None


def debt_cycle(asof: date, data=None):
    """Indicators of Dalio's long-term (big) debt cycle, the warning signals he calls the classic template for
    government bond markets, and a stage call."""
    data = data or load()
    yr = asof - timedelta(days=365)
    three = asof - timedelta(days=3 * 365)
    ind, sig = [], []

    def add(key, label, pts, unit, note, dec=1):
        now, then = last(pts), at(pts, three)
        if not now:
            return None
        row = {"key": key, "label": label, "now": round(now[1], dec), "now_date": now[0].isoformat(), "unit": unit,
               "then": then and round(then[1], dec), "then_date": then and then[0].isoformat(), "note": note}
        ind.append(row)
        return row

    dg = add("debt_gdp", "Federal debt held by the public, % of GDP", data["debt_gdp"], "%", "FRED FYGFGDQ188S")
    ir = add("int_rev", "Federal interest payments, % of federal receipts", data["int_rev"], "%", "FRED A091RC1Q027SBEA / W006RC1Q027SBEA")
    ig = add("int_gdp", "Net interest outlays, % of GDP", data["int_gdp"], "%", "FRED FYOIGDA188S", 2)
    df = add("deficit", "Federal surplus or deficit, % of GDP", data["deficit"], "%", "FRED FYFSGDA188S")
    g10, ng = last(data["gs10"]), last(data["ngdp_yoy"])
    if g10 and ng:
        ind.append({"key": "r_g", "label": "10Y yield minus nominal GDP growth (r − g)", "now": round(g10[1] - ng[1], 1),
                    "now_date": ng[0].isoformat(), "unit": "pt", "then": None, "then_date": None,
                    "note": f"10Y {g10[1]:.2f}% ({_m(g10[0])}) minus nominal GDP growth {ng[1]:.1f}% y/y ({_m(ng[0])})"})
    fs = add("fed_share", "Fed holdings, % of debt held by the public", data["fed_share"], "%", "FRED TREAST / FYGFDPUN")
    fo = add("foreign_share", "Foreign holdings, % of debt held by the public", data["foreign_share"], "%", "FRED FDHBFIN / FYGFDPUN")
    curve = [(t, v - at(data["gs2"], t)[1]) for t, v in data["gs30"] if at(data["gs2"], t)]
    tp = add("slope", "30Y minus 2Y yield, monthly average", curve, "pt", "FRED GS30 minus GS2", 2)
    rl = add("real10", "10Y real yield (TIPS), monthly average", data["real10"], "%", "FRED DFII10", 2)

    def chg12(pts):
        now, then = last(pts), at(pts, yr)
        return (now[1] / then[1] - 1) * 100 if now and then else None

    dollar_chg = chg12(data["dollar"])
    gold_chg = chg12(data["gold"])
    y10_now, y10_then = last(data["gs10"]), at(data["gs10"], yr)
    y10_chg = (y10_now[1] - y10_then[1]) * 100 if y10_now and y10_then else None
    s10, s30 = at(data["gs30"], asof), at(data["gs30"], yr)
    l10 = (s10[1] - y10_now[1]) - (s30[1] - y10_then[1]) if s10 and s30 and y10_now and y10_then else None  # 10s30s change

    def signal(name, on, evidence):
        sig.append({"signal": name, "on": bool(on), "evidence": evidence})

    signal("Debt is high and rising", dg and dg["now"] >= 90 and (dg["then"] is None or dg["now"] >= dg["then"]),
           f"Debt held by the public {dg['now']:.0f}% of GDP ({_m(date.fromisoformat(dg['now_date']))}) vs {dg['then']:.0f}% three years earlier" if dg and dg["then"] else "n/a")
    signal("Debt service is outgrowing revenue", ir and ir["then"] and ir["now"] > ir["then"] + 1,
           f"Interest takes {ir['now']:.1f}% of federal receipts ({_m(date.fromisoformat(ir['now_date']))}) vs {ir['then']:.1f}% three years earlier" if ir and ir["then"] else "n/a")
    rg = next((x for x in ind if x["key"] == "r_g"), None)
    signal("Borrowing costs exceed growth (r > g)", rg and rg["now"] > 0, rg["note"] + f" = {rg['now']:+.1f}pt" if rg else "n/a")
    signal("Long-term yields rising faster than short-term ones", tp and tp["then"] is not None and tp["now"] > tp["then"] + 0.25,
           f"30Y minus 2Y {tp['now']:+.2f}pt ({_m(date.fromisoformat(tp['now_date']))}) vs {tp['then']:+.2f}pt three years earlier" if tp and tp["then"] is not None else "n/a")
    signal("Yields up while the dollar weakens", y10_chg is not None and dollar_chg is not None and y10_chg > 25 and dollar_chg < -2,
           f"Over 12 months: 10Y {y10_chg:+.0f}bp, broad dollar index {dollar_chg:+.1f}%" if y10_chg is not None and dollar_chg is not None else "n/a")
    signal("Foreign buyers are stepping back", fo and fo["then"] and fo["now"] < fo["then"] - 1,
           f"Foreign share {fo['now']:.1f}% ({_m(date.fromisoformat(fo['now_date']))}) vs {fo['then']:.1f}% three years earlier" if fo and fo["then"] else "n/a")
    signal("Gold outperforms as a hedge against the currency", gold_chg is not None and gold_chg > 10,
           f"Gold {gold_chg:+.1f}% over 12 months" if gold_chg is not None else "n/a")
    signal("Large deficits outside a recession", df and df["now"] <= -5,
           f"Deficit {abs(df['now']):.1f}% of GDP (fiscal {date.fromisoformat(df['now_date']).year})" if df else "n/a")

    on = sum(x["on"] for x in sig)
    # Structural signals describe where the cycle is; stress signals describe whether bond buyers are pulling back.
    structural = [sig[0], sig[3], sig[7]]
    stress = [sig[1], sig[2], sig[4], sig[5], sig[6]]
    s_on, x_on = sum(x["on"] for x in structural), sum(x["on"] for x in stress)
    mp_now = mp_regime(asof, data["ff"], data["walcl_yoy"], data["deficit"])
    on_names = lambda xs: ", ".join(x["signal"].lower() for x in xs if x["on"]) or "none"
    off_names = lambda xs: ", ".join(x["signal"].lower() for x in xs if not x["on"]) or "none"
    if dg and dg["now"] >= 90 and s_on >= 2:
        stage = ("Late stage, with the classic stress signals building" if x_on >= 4 else
                 "Late stage, with early signs of bond-market stress" if x_on >= 2 else
                 "Late stage, without bond-market stress so far")
        call = (f"Structurally this is the late stage of Dalio's long-term debt cycle: {on_names(structural)}. "
                f"Stress signals on: {on_names(stress)}. Not yet on: {off_names(stress)}. "
                + ("That is the classic template of a government bond market losing buyers, which historically ends in "
                   "restructuring, monetization or inflation." if x_on >= 4 else
                   "Investors are asking more to lend for long, but buyers have not stepped back; a weaker dollar with "
                   "rising yields and falling foreign demand would mark the next stage."))
    elif dg and dg["now"] >= 60:
        stage = "Mid stage of the long-term debt cycle"
        call = f"Debt is elevated ({dg['now']:.0f}% of GDP) but only {on} of {len(sig)} warning signals are on."
    else:
        stage = "Early stage of the long-term debt cycle"
        call = f"Debt is moderate and {on} of {len(sig)} warning signals are on; there is room for fiscal and monetary policy."
    return {"stage": stage, "call": call, "signals_on": on, "signals_total": len(sig), "signals": sig,
            "indicators": ind, "mp_now": mp_now, "mp_text": MP_TEXT[mp_now],
            "dollar_12m": dollar_chg and round(dollar_chg, 1), "gold_12m": gold_chg and round(gold_chg, 1)}


# ---------------------------------------------------------------------------
# The long-window story (same shape as story.build, so the page layout never changes)
# ---------------------------------------------------------------------------
WHEN = lambda a, P0: {"1D": "Over the past day", "1W": "Over the past week", "1M": "Over the past month",
                      "3M": "Over the past three months", "1Y": "Over the past year"}.get(a["horizon"], f"Since {P0}")

FORCES = {
    "rstar": {
        "name": "The neutral real rate (r*)", "channel": "Floor under real yields",
        "mechanism": "The neutral real rate is the inflation-adjusted short rate that neither stimulates nor slows the "
                     "economy (Wicksell; Laubach-Williams). It fell for decades as ageing populations saved more, "
                     "emerging-market savings flowed into US bonds (Bernanke's global savings glut), and productivity and "
                     "investment demand slowed (Summers' secular stagnation). Bank of England research attributes about "
                     "400bp of the fall in global real rates since the 1980s to such forces. Goodhart and Pradhan argue "
                     "ageing now reverses it as workers become scarce. Long yields price the average expected short rate, "
                     "so r* sets their floor.",
        "links": [("New York Fed: measuring the natural rate of interest", "https://www.newyorkfed.org/research/policy/rstar")],
    },
    "inflation": {
        "name": "The inflation regime", "channel": "Inflation compensation",
        "mechanism": "By the Fisher equation, nominal yields carry expected inflation. From the 1990s the Fed's "
                     "credibility anchored long-run expectations near 2% (the Great Moderation). If long-run expectations "
                     "stay anchored, inflation shocks move the front end through the Fed rather than the long end; if they "
                     "drift, breakevens and the whole curve reprice.",
        "links": [("Cleveland Fed: inflation expectations", "https://www.clevelandfed.org/indicators-and-data/inflation-expectations")],
    },
    "debtcycle": {
        "name": "The long-term debt cycle and term premium", "channel": "Term premium",
        "mechanism": "In Ray Dalio's long-term debt cycle, each short-term cycle leaves debt higher until servicing it "
                     "squeezes incomes. Policy moves from rate cuts (MP1) to QE (MP2) to QE financing deficits (MP3). QE took "
                     "duration out of the market and compressed term premium after 2008; the end of QE, heavy issuance and "
                     "doubts about fiscal discipline put it back. In How Countries Go Broke, the classic signs of a government "
                     "bond market losing buyers are rising long-end yields with a weaker currency, foreign selling and "
                     "central-bank support.",
        "links": [("Ray Dalio: How Countries Go Broke (2025)", "https://www.economicprinciples.org/"),
                  ("Fed Board: Kim-Wright term premium", "https://www.federalreserve.gov/data/three-factor-nominal-term-structure-model.htm")],
    },
}


def _verdict(bp):
    if bp is None:
        return "Not available", "n/a"
    if bp <= -25:
        return "Pulled yields down", f"{bp:+.0f}bp"
    if bp >= 25:
        return "Pushed yields up", f"{bp:+.0f}bp"
    return "Little net effect", f"{bp:+.0f}bp"


def _mp_spans(rows):
    """Contiguous monetary-policy regimes along a monthly path: [('MP2', 'Dec 2008', 'Oct 2015'), ...]."""
    out = []
    for r in rows:
        d = date.fromisoformat(r["d"])
        if out and out[-1][0] == r["mp"]:
            out[-1][2] = d
        else:
            out.append([r["mp"], d, d])
    return out


def fed_cycles(past: date, asof: date):
    """Group target-rate changes into easing and tightening cycles: [('cut', 225, date0, date1), ...]."""
    pts = fred("DFEDTARU", date(2008, 12, 1))
    moves, prev = [], None
    for d, v in pts:
        if prev is not None and v != prev and past < d <= asof:
            moves.append((d, round((v - prev) * 100)))
        prev = v
    out = []
    for d, bp in moves:
        kind = "hike" if bp > 0 else "cut"
        if out and out[-1][0] == kind:
            out[-1][1] += abs(bp); out[-1][3] = d
        else:
            out.append([kind, abs(bp), d, d])
    return out


def build_long(a, mode, sc, fed, auctions, data, dec, dc, lg, watch, brief_data):
    k = sc["by_key"]
    T = {t["tenor"]: t for t in a["tenors"]}
    d2, d10, d30 = (T[x]["chg_bp"] or 0 for x in ("2Y", "10Y", "30Y"))
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    P0, P1 = _d(past), _d(asof)
    when = WHEN(a, P0)
    yrs = (asof - past).days / 365.25
    s2 = a["spreads"]["2s10s"]
    daily = [(t, v) for t, v in fred("DGS10", past) if past <= t <= asof]
    lo = min(daily, key=lambda x: x[1]) if daily else None
    hi = max(daily, key=lambda x: x[1]) if daily else None
    st, en, ch = dec.get("start") or {}, dec.get("end") or {}, dec.get("chg_bp") or {}
    sec = sum(ch.get(x, 0) for x in ("rstar", "einf", "tp")) if ch else None
    cyc = ch.get("residual")
    fair_now = round(en["anchor"] + (en.get("tp") or 0), 2) if en.get("anchor") is not None else None

    # Headline: same template idea as the near-term story (move, path, main driver).
    path_txt = (f" by way of a {lo[1]:.2f}% low ({_m(lo[0])}) and a {hi[1]:.2f}% high ({_m(hi[0])})" if lo and hi else "")
    if sec is not None and cyc is not None:
        lead = "secular" if abs(sec) >= abs(cyc) else "cyclical"
        driver = (f"driven mainly by secular forces ({sec:+.0f}bp from the neutral rate, expected inflation and term premium) "
                  f"rather than the policy gap ({cyc:+.0f}bp)" if lead == "secular" else
                  f"driven mainly by the policy gap ({cyc:+.0f}bp of expected policy versus neutral) rather than secular forces ({sec:+.0f}bp)")
    else:
        lead, driver = "n/a", "with the secular decomposition unavailable this far back"
    cycles = fed_cycles(past, asof)
    cyc_txt = ", ".join(f"{'hiked' if k_ == 'hike' else 'cut'} {bp}bp ({_m(d0)}{'' if d0 == d1 else '–' + _m(d1)})" for k_, bp, d0, d1 in cycles)
    if mode == "cyclical":
        big = sorted(lg, key=lambda l: -abs(l["chg_bp"]))[:2]
        big = sorted(big, key=lambda l: l["from"])
        moves_txt = ", then ".join(f"{'rose' if l['chg_bp'] > 0 else 'fell'} to {l['y_to']:.2f}% by {_m(date.fromisoformat(l['to']))}"
                                   + (f" ({l['history'][0].split(':')[0].split(';')[0]})" if l["history"] else "") for l in big)
        backdrop = (f"; underneath, the secular anchor moved {sec:+.0f}bp (neutral rate {ch.get('rstar', 0):+.0f}bp, expected inflation "
                    f"{ch.get('einf', 0):+.0f}bp, term premium {ch.get('tp', 0):+.0f}bp)" if sec is not None else "")
        headline = (f"{when}, the 10Y went from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}% ({d10:+.0f}bp) across {len(lg)} "
                    f"cycles: it {moves_txt}{backdrop}.")
    else:
        headline = (f"{when}, the 10Y went from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}% ({d10:+.0f}bp){path_txt}, {driver}.")

    # Cycles in between
    def leg_txt(l):
        verb = "rose" if l["chg_bp"] > 0 else "fell"
        h = f" ({l['history'][0]})" if l["history"] else ""
        return f"{verb} {abs(l['chg_bp'])}bp to {l['y_to']:.2f}% by {_m(date.fromisoformat(l['to']))}{h}"
    legs_txt = "; ".join(leg_txt(l) for l in lg)
    spans = [s for s in _mp_spans(path(past, asof, data)) if (s[2] - s[1]).days > 60]
    mp_txt = "; ".join(f"{m} {_m(s0)}–{_m(s1)}" for m, s0, s1 in spans) or "MP1 throughout"

    rs0, rs1 = st.get("rstar"), en.get("rstar")
    e0, e1 = st.get("einf"), en.get("einf")
    tp0, tp1 = st.get("tp"), en.get("tp")
    res0, res1 = st.get("residual"), en.get("residual")
    m0 = _m(date.fromisoformat(st["date"])) if st else P0
    m1 = _m(date.fromisoformat(en["date"])) if en else P1
    cpi0 = at(data["cpi_yoy"], past); cpi1 = last(data["cpi_yoy"])

    brief = [
        {"label": "Move", "text": f"10Y {T['10Y']['past']:.2f}% ({P0}) → {T['10Y']['today']:.2f}% ({P1}), {d10:+.0f}bp"
                                  + (f"; low {lo[1]:.2f}% ({_d(lo[0])}), high {hi[1]:.2f}% ({_d(hi[0])})" if lo and hi else "")
                                  + f"; 2Y {d2:+.0f}bp, 30Y {d30:+.0f}bp; 2s10s {s2['past']:+.0f}bp → {s2['today']:+.0f}bp."},
        {"label": "Why", "text": (f"Secular {sec:+.0f}bp: neutral rate {ch.get('rstar', 0):+.0f}bp ({rs0:.2f}% → {rs1:.2f}%), expected inflation "
                                  f"{ch.get('einf', 0):+.0f}bp, term premium {ch.get('tp', 0):+.0f}bp. Policy gap {cyc:+.0f}bp. "
                                  f"Secular fair value today ≈ {fair_now:.2f}% vs a {en['y10']:.2f}% 10Y ({m1} averages)."
                                  if sec is not None and rs0 is not None and rs1 is not None and fair_now is not None else
                                  "Secular decomposition unavailable for this start date (expected-inflation data begins 1982, term premium 1990).")},
        {"label": "Data", "text": brief_data},
        {"label": "Themes", "text": f"Neutral rate ({_verdict(ch.get('rstar'))[0].lower()}) · inflation regime "
                                    f"({_verdict(ch.get('einf'))[0].lower()}) · long-term debt cycle: {dc['stage'].lower()} "
                                    f"({dc['signals_on']} of {dc['signals_total']} warning signals)."},
        {"label": "Next", "text": " · ".join(f"{date.fromisoformat(w['when']):%b} {date.fromisoformat(w['when']).day} {w['short']}" for w in watch[:4]) + "."
                                  if watch else "No FOMC meeting or coupon auction in the next two weeks."},
    ]

    summary = [
        {"label": "What happened", "metric": f"10Y {d10:+.0f}bp over {yrs:.0f} years, {len(lg)} cycles",
         "text": f"Between the {P0} and {P1} closes the 10Y went from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}%. "
                 f"The endpoints hide the path. By monthly average it {legs_txt}."},
        {"label": "Monetary", "metric": (f"Neutral rate {ch.get('rstar', 0):+.0f}bp · expected inflation {ch.get('einf', 0):+.0f}bp" if ch else "n/a"),
         "text": " ".join(x for x in [
             f"Neutral rate: the Laubach-Williams r* went from {rs0:.2f}% ({_m(date.fromisoformat(st['rstar_date']))}) to {rs1:.2f}% "
             f"({_m(date.fromisoformat(en['rstar_date']))})." if rs0 is not None and rs1 is not None else "",
             f"Inflation regime: expected 10-year inflation (Cleveland Fed) went from {e0:.2f}% ({m0}) to {e1:.2f}% ({m1}); "
             f"CPI inflation from {cpi0[1]:.1f}% ({_m(cpi0[0])}) to {cpi1[1]:.1f}% ({_m(cpi1[0])})." if e0 is not None and cpi0 else "",
             f"Fed cycles in the window: the Fed {cyc_txt}." if cycles else "",
             f"Policy regimes (Dalio's MP1–MP3): {mp_txt}.",
             f"The policy gap (10Y minus r*, expected inflation and term premium: expected policy versus neutral, plus model error) went "
             f"from {res0:+.2f}pt to {res1:+.2f}pt, so markets now price policy {'above' if res1 > 0 else 'below'} neutral over ten years."
             if res0 is not None and res1 is not None else ""] if x)},
        {"label": "Fiscal and global", "metric": (f"Term premium {ch['tp']:+.0f}bp" if "tp" in ch else "Term premium: no data before 1990"),
         "text": " ".join(x for x in [
             f"Term premium (Kim-Wright) went from {tp0:.2f}% ({m0}) to {tp1:.2f}% ({m1})." if tp0 is not None and tp1 is not None else "",
             f"Debt held by the public: {at(data['debt_gdp'], past)[1]:.0f}% of GDP ({_m(at(data['debt_gdp'], past)[0])}) to "
             f"{last(data['debt_gdp'])[1]:.0f}% ({_m(last(data['debt_gdp'])[0])})." if at(data['debt_gdp'], past) else "",
             f"Long-term debt cycle: {dc['stage'].lower()}. {dc['call']}"] if x)},
        {"label": "The themes behind it", "metric": "Three secular forces",
         "text": f"The neutral real rate ({_verdict(ch.get('rstar'))[1]}), the inflation regime ({_verdict(ch.get('einf'))[1]}) and the long-term "
                 f"debt cycle through term premium ({_verdict(ch.get('tp'))[1]}). Over windows this long, news headlines are not a reliable "
                 f"guide; the cycles and dated history above replace them."},
        {"label": "What to watch", "metric": f"Next: {_d(date.fromisoformat(watch[0]['when']))}" if watch else "No scheduled catalysts found",
         "text": " ".join(f"{_d(date.fromisoformat(w['when']))}: {w['what']}" for w in watch[:4]) or "No FOMC meeting or coupon auction in the next two weeks."},
    ]

    deck = [f"Monthly averages, {m0} to {m1}: 10Y {ch.get('y10', 0):+.0f}bp = neutral rate {ch.get('rstar', 0):+.0f}bp + expected inflation "
            f"{ch.get('einf', 0):+.0f}bp + term premium {ch.get('tp', 0):+.0f}bp + policy gap and residual {ch.get('residual', 0):+.0f}bp."
            if ch and "residual" in ch else "Secular decomposition: not available for this start date.",
            (f"Secular fair value (r* {rs1:.2f}% + expected inflation {e1:.2f}% + term premium {tp1:.2f}%) ≈ {fair_now:.2f}% vs a "
             f"{en['y10']:.2f}% 10Y ({m1})." if fair_now is not None and tp1 is not None else "Secular fair value: n/a."),
            f"{P0} to {P1}: 2Y {d2:+.0f}bp, 10Y {d10:+.0f}bp, 30Y {d30:+.0f}bp; 2s10s {s2['chg'] or 0:+.0f}bp."]

    risks = []
    if res1 is not None and fair_now is not None:
        risks.append(f"The 10Y is {abs(res1) * 100:.0f}bp {'above' if res1 > 0 else 'below'} its secular fair value of about {fair_now:.2f}%. "
                     + ("A turn in the Fed cycle toward neutral would pull it lower." if res1 > 0 else
                        "If policy normalizes toward neutral, yields have room to rise."))
    risks.append("The stress signals in Dalio's template (a weaker dollar with rising yields, foreign selling, central-bank "
                 "support) are the ones to watch; if they turn on, term premium can jump." if dc["signals_on"] < 6 else
                 "Most of Dalio's warning signals are on: term premium could jump abruptly.")
    risks.append("r* is a model estimate with wide error bands, and the main models have disagreed sharply since 2022.")

    themes = []
    for key, comp in (("rstar", "rstar"), ("inflation", "einf"), ("debtcycle", "tp")):
        f = FORCES[key]
        verdict, bp = _verdict(ch.get(comp))
        life = {"rstar": f"Laubach-Williams r* {rs0:.2f}% to {rs1:.2f}% (quarterly estimates, {m0} to {m1})." if rs0 is not None and rs1 is not None else "",
                "inflation": (f"Expected 10-year inflation {e0:.2f}% to {e1:.2f}% ({m0} to {m1}); CPI {cpi0[1]:.1f}% to {cpi1[1]:.1f}%."
                              if e0 is not None and cpi0 else ""),
                "debtcycle": f"{dc['stage']}: {dc['signals_on']} of {dc['signals_total']} warning signals on. Policy regime now: {dc['mp_text']}."}[key]
        themes.append({"key": key, "name": f["name"], "channel": f["channel"], "mechanism": f["mechanism"], "volume": None,
                       "life": life, "verdict": verdict, "evidence": f"Contribution to the 10Y over the window: {bp} (monthly averages, {m0} to {m1}).",
                       "headlines": [], "links": [{"title": t, "url": u} for t, u in f["links"]]})

    # Evidence lists for the long view
    def span(pts, label, unit="%", dec_=2):
        p0, p1 = at(pts, past), last(pts)
        if not p1:
            return None
        if not p0:
            return f"{label} {p1[1]:.{dec_}f}{unit} ({_m(p1[0])}); no data at the start of the window"
        return f"{label} {p0[1]:.{dec_}f}{unit} ({_m(p0[0])}) to {p1[1]:.{dec_}f}{unit} ({_m(p1[0])})"
    mon = [x for x in [
        {"label": "Fed funds", "push": "flat", "text": span(data["ff"], "Effective fed funds rate, monthly average,") + "."},
        {"label": "Neutral rate", "push": "down" if (ch.get("rstar") or 0) < -25 else "up" if (ch.get("rstar") or 0) > 25 else "flat",
         "text": (span(data["rstar"], "Laubach-Williams r*") or "n/a") + "."},
        {"label": "Expectations", "push": "down" if (ch.get("einf") or 0) < -25 else "up" if (ch.get("einf") or 0) > 25 else "flat",
         "text": (span(data["einf"], "Expected 10-year inflation (Cleveland Fed)") or "n/a") + "."},
        {"label": "Inflation", "push": "flat", "text": (span(data["cpi_yoy"], "CPI inflation, year over year,", "%", 1) or "n/a") + "."},
        {"label": "Fed balance sheet", "push": "flat", "text": (span(data["fed_share"], "Fed holdings as a share of debt held by the public", "%", 1) or "n/a") + f". Regimes: {mp_txt}."},
    ] if x["text"]]
    fis = [x for x in [
        {"label": "Term premium", "push": "down" if (ch.get("tp") or 0) < -25 else "up" if (ch.get("tp") or 0) > 25 else "flat",
         "text": (span(data["tp"], "Kim-Wright 10Y term premium, monthly average,") or "No term-premium data before 1990") + "."},
        {"label": "Debt", "push": "up", "text": (span(data["debt_gdp"], "Federal debt held by the public, % of GDP,", "%", 0) or "n/a") + "."},
        {"label": "Debt service", "push": "flat", "text": (span(data["int_rev"], "Federal interest payments as a share of receipts", "%", 1) or "n/a") + "."},
        {"label": "Foreign demand", "push": "flat", "text": (span(data["foreign_share"], "Foreign holdings as a share of debt held by the public", "%", 1) or "n/a") + "."},
        {"label": "Dalio's call", "push": "flat", "text": f"{dc['stage']}. {dc['call']}"},
    ] if x["text"]]

    return {"headline": headline, "brief": brief, "summary": summary, "deck": deck, "monetary": mon, "fiscal": fis,
            "themes": themes, "all_themes": [], "surprises": [], "watch": watch, "risks": risks, "lead": lead,
            "window": {"from": P0, "to": P1}, "thesis": [x["label"] + ": " + x["text"] for x in summary[1:3]]}
