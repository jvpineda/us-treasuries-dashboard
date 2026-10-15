"""The tape: how big a move is, judged the way a macro desk judges it.

A 5bp day and a 5bp year are not the same thing. Every move is scaled by the asset's own realized volatility over the
year before the window (sigma = daily standard deviation x sqrt(trading days in the window)), so 1D and 1W windows are
called noise when they are noise. Rates moves are also placed in history ("largest 1-year rise in the 2Y since ..."),
and the cross-asset tape (equities, dollar, oil, gold, VIX, MOVE) says what kind of rates move it was.
"""
from __future__ import annotations

import bisect
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import sources as S

RATE_SERIES = {"2Y": "DGS2", "10Y": "DGS10", "30Y": "DGS30", "real10": "DFII10", "be10": "T10YIE"}
CROSS = [("^GSPC", "S&P 500", "pct"), ("DX-Y.NYB", "Dollar (DXY)", "pct"), ("CL=F", "WTI oil", "pct"),
         ("GC=F", "Gold", "pct"), ("^VIX", "VIX", "pts"), ("^MOVE", "MOVE", "pts")]
VOL_DAYS = 252


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def _fred_all():
    def load():
        with ThreadPoolExecutor(5) as ex:
            res = dict(zip(RATE_SERIES, ex.map(lambda sid: _try(S.fred, sid, date(1976, 1, 1)) or [], RATE_SERIES.values())))
        return res
    return S.cached("tape_fred", 6 * 3600, load)


def trading_days(past: date, asof: date) -> int:
    n, d = 0, past
    while d < asof:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return max(n, 1)


def _daily_sigma(pts, end: date, log=False, scale=1.0):
    """Std dev of daily changes over the VOL_DAYS observations up to `end`."""
    xs = [v for d, v in pts if d <= end][-(VOL_DAYS + 1):]
    if len(xs) < 40:
        return None
    ch = [(math.log(b / a) if log else (b - a)) * scale for a, b in zip(xs, xs[1:]) if (a > 0 and b > 0) or not log]
    m = sum(ch) / len(ch)
    return math.sqrt(sum((c - m) ** 2 for c in ch) / (len(ch) - 1))


def _at(pts, d):
    ds = [p[0] for p in pts]
    i = bisect.bisect_right(ds, d) - 1
    return pts[i] if i >= 0 else None


def largest_since(pts, past: date, asof: date, move_bp: float):
    """Most recent window of the same length, ending before this one starts, with a move at least as large in the
    same direction. None means none since the series began."""
    h = asof - past
    ds = [p[0] for p in pts]
    sign = 1 if move_bp > 0 else -1
    for i in range(bisect.bisect_right(ds, past) - 1, -1, -1):
        t, v = pts[i]
        j = bisect.bisect_right(ds, t - h) - 1
        if j < 0:
            break
        if (v - pts[j][1]) * 100 * sign >= abs(move_bp):
            return {"date": t.isoformat(), "from": pts[j][0].isoformat(), "bp": round((v - pts[j][1]) * 100)}
    return {"date": None, "since": pts[0][0].isoformat()}


def level_since(pts, asof: date, up: bool, level: float | None = None):
    """'Highest since Jul 2007': the last date before the past month when the level was at least (or at most) today's."""
    now = (asof, level) if level is not None else _at(pts, asof)
    if not now:
        return None
    for t, v in reversed(pts):
        if t >= asof - timedelta(days=30):
            continue
        if (v >= now[1]) if up else (v <= now[1]):
            return {"date": t.isoformat(), "level": v, "now": now[1]}
    return {"date": None, "since": pts[0][0].isoformat(), "now": now[1]}


def rates(a: dict) -> dict:
    """Rates moves from the par curve, scaled by trailing realized volatility from the H.15 daily series."""
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    n = trading_days(past, asof)
    fr = _fred_all()
    T = {t["tenor"]: t for t in a["tenors"]}
    at = a["attribution"]
    s2 = a["spreads"]["2s10s"]
    curve2s10s = [(d, v - _at(fr["2Y"], d)[1]) for d, v in fr["10Y"] if _at(fr["2Y"], d)] if fr["10Y"] and fr["2Y"] else []
    rows = []

    def add(key, label, chg, pts, then=None, now=None, hist=True):
        sd = _daily_sigma(pts, past, scale=100) if pts else None
        sig = sd * math.sqrt(n) if sd else None
        z = chg / sig if sig and chg is not None else None
        row = {"key": key, "label": label, "chg_bp": chg, "then": then, "now": now, "sd_daily_bp": sd and round(sd, 2),
               "sigma_bp": sig and round(sig, 1), "z": z and round(z, 2), "n_days": n}
        if hist and pts and chg and abs(chg) >= 1:
            row["largest_since"] = largest_since(pts, past, asof, chg)
        rows.append(row)

    add("2Y", "2Y", T["2Y"]["chg_bp"], fr["2Y"], T["2Y"]["past"], T["2Y"]["today"])
    add("10Y", "10Y", T["10Y"]["chg_bp"], fr["10Y"], T["10Y"]["past"], T["10Y"]["today"])
    add("30Y", "30Y", T["30Y"]["chg_bp"], fr["30Y"], T["30Y"]["past"], T["30Y"]["today"], hist=False)
    add("2s10s", "2s10s", s2["chg"], curve2s10s, s2["past"], s2["today"], hist=False)
    x10 = at.get("10Y") or {}
    if at.get("real_bp") is not None:
        add("real10", "10Y real", at["real_bp"], fr["real10"], round(x10["real"] - at["real_bp"] / 100, 2), x10.get("real"), hist=False)
        add("be10", "10Y breakeven", at["be_bp"], fr["be10"], round(x10["breakeven"] - at["be_bp"] / 100, 2), x10.get("breakeven"), hist=False)
    lead = max((r for r in rows if r["key"] in ("2Y", "10Y") and r["z"] is not None), key=lambda r: abs(r["z"]), default=None)
    up = (T["10Y"]["chg_bp"] or 0) >= 0
    lv = {k: level_since(fr[k], asof, up, T[k]["today"]) for k in ("2Y", "10Y") if fr[k]}
    return {"rows": rows, "lead": lead, "n_days": n, "levels": lv, "grade": grade(lead["z"] if lead else None)}


def grade(z):
    if z is None:
        return {"label": "n/a", "cls": ""}
    a = abs(z)
    if a < 1:
        return {"label": "Noise", "cls": "", "note": "inside one standard deviation of normal trading"}
    if a < 2:
        return {"label": "Notable", "cls": "solid", "note": "one to two standard deviations"}
    if a < 3:
        return {"label": "Big move", "cls": "bear" if z > 0 else "bull", "note": "two to three standard deviations"}
    return {"label": "Extreme", "cls": "bear" if z > 0 else "bull", "note": "more than three standard deviations"}


def cross_asset(past: date, asof: date) -> list:
    """Equities, dollar, oil, gold and volatility over the same window, each scaled by its own realized volatility."""
    yrs = (asof - past).days / 365.25
    syms = [c[0] for c in CROSS]
    if yrs <= 1.9:
        data = _try(S.yahoo_spark, syms, "5y") or _try(S.yahoo_spark, syms, "2y") or {}
    else:
        rng = "10y" if yrs <= 9.5 else "max"
        with ThreadPoolExecutor(6) as ex:
            data = dict(zip(syms, ex.map(lambda s: _try(S.yahoo_chart, s, rng) or _try(S.yahoo_chart, s, "max"), syms)))
    n = trading_days(past, asof)
    out = []
    for sym, label, kind in CROSS:
        c = data.get(sym)
        if not c or not c.get("hist"):
            continue
        hist = [(d, v) for d, v in c["hist"] if v]
        p0, p1 = _at(hist, past), hist[-1]
        if not p0 or p0[0] < past - timedelta(days=10):
            continue
        if kind == "pct":
            chg = (p1[1] / p0[1] - 1) * 100
            sd = _daily_sigma(hist, past, log=True, scale=100)
        else:
            chg = p1[1] - p0[1]
            sd = _daily_sigma(hist, past)
        sig = sd * math.sqrt(n) if sd and yrs <= 1.9 else None
        out.append({"sym": sym, "label": label, "kind": kind, "then": round(p0[1], 2), "then_date": p0[0].isoformat(),
                    "now": round(p1[1], 2), "now_date": p1[0].isoformat(), "chg": round(chg, 1 if kind == "pct" else 1),
                    "sd_daily": sd and round(sd, 2), "sigma": sig and round(sig, 2), "z": round(chg / sig, 2) if sig else None,
                    "n_days": n})
    return out


def front_end(a: dict, k: dict) -> str | None:
    """The 2Y against the fed funds midpoint at both ends of the window: the cleanest read of cuts vs hikes priced."""
    t2 = {t["tenor"]: t for t in a["tenors"]}.get("2Y")
    ff = k.get("fedfunds")
    if not t2 or not ff or not ff.get("then"):
        return None
    g0 = (t2["past"] - (ff["then"]["value"] - 0.125)) * 100
    g1 = (t2["today"] - (ff["now"]["value"] - 0.125)) * 100
    side = lambda g: f"{abs(g):.0f}bp {'below' if g < 0 else 'above'}"
    tag = ("flipped from pricing cuts to pricing hikes" if g0 < -15 and g1 > 15 else
           "flipped from pricing hikes to pricing cuts" if g0 > 15 and g1 < -15 else
           "priced in more tightening" if g1 - g0 > 15 else "priced in more easing" if g1 - g0 < -15 else "barely moved")
    return f"the 2Y went from {side(g0)} fed funds to {side(g1)}: the front end {tag}"


def regime_read(d10: float, rows: list, x: list) -> dict | None:
    """What kind of rates move it was, from how equities and the dollar traded alongside it."""
    by = {r["sym"]: r for r in x}
    spx, dxy = by.get("^GSPC"), by.get("DX-Y.NYB")
    if not spx or abs(d10 or 0) < 1:
        return None
    eq_up, y_up = spx["chg"] > 0, d10 > 0
    if y_up and eq_up:
        name, read = "Growth-led selloff", "stocks rallied with yields, so the market is treating strong data as good news, not a threat"
    elif y_up:
        name, read = "Rates shock", "stocks fell as yields rose: good news is bad news, higher rates are tightening financial conditions"
    elif eq_up:
        name, read = "Goldilocks rally", "yields fell while stocks rose: a disinflation or easier-Fed rally"
    else:
        name, read = "Risk-off", "yields fell with stocks: bonds are hedging equities, a growth scare"
    fx = ""
    if dxy:
        if y_up and dxy["chg"] > 0:
            fx = "The dollar confirmed it (DXY up): US rates are pulling in capital."
        elif y_up and dxy["chg"] < 0:
            fx = "The dollar did not confirm (DXY down while yields rose): a credibility or fiscal tell worth watching."
        elif not y_up and dxy["chg"] < 0:
            fx = "The dollar fell with yields, consistent with an easier Fed."
        else:
            fx = "The dollar rose as yields fell: a haven bid."
    return {"name": name, "read": read, "fx": fx}
