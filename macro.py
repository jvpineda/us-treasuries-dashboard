"""Macro evidence: the data a rates desk checks when explaining a curve move.

Every value is taken "as known" on a date: an observation counts only once its typical release lag has passed,
so the start of a window shows what the market actually knew then (no look-ahead).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import sources as S

# key, label, group, FRED id, transform, unit, decimals, push
#   push: +1 if a rise in the indicator pushes Treasury yields up, -1 if down, 0 if it is a consequence, not a cause.
INDICATORS = [
    ("cpi", "Headline CPI", "Inflation", "CPIAUCSL", "yoy", "% y/y", 1, +1),
    ("core_cpi", "Core CPI", "Inflation", "CPILFESL", "yoy", "% y/y", 1, +1),
    ("core_cpi_3m", "Core CPI, 3-month annualized", "Inflation", "CPILFESL", "ann3m", "%", 1, +1),
    ("core_pce", "Core PCE (the Fed's gauge)", "Inflation", "PCEPILFE", "yoy", "% y/y", 1, +1),
    ("core_goods", "Core goods CPI (tariff pass-through)", "Inflation", "CUSR0000SACL1E", "yoy", "% y/y", 1, +1),
    ("wages", "Average hourly earnings", "Inflation", "CES0500000003", "yoy", "% y/y", 1, +1),
    ("mich", "Consumers' 1-year inflation expectation", "Expectations", "MICH", "level", "%", 1, +1),
    ("fwd5y5y", "5y5y forward breakeven", "Expectations", "T5YIFR", "level", "%", 2, +1),
    ("gdp", "Real GDP growth", "Growth & jobs", "A191RL1Q225SBEA", "level", "% saar", 1, +1),
    ("payrolls", "Payroll growth, 3-month average", "Growth & jobs", "PAYEMS", "diff3avg", "k/mo", 0, +1),
    ("unrate", "Unemployment rate", "Growth & jobs", "UNRATE", "level", "%", 1, -1),
    ("claims", "Initial jobless claims, 4-week avg", "Growth & jobs", "IC4WSA", "thousands", "k", 0, -1),
    ("fedfunds", "Fed funds target, upper bound", "Policy & fiscal", "DFEDTARU", "level", "%", 2, +1),
    ("deficit", "Federal deficit, rolling 12 months", "Policy & fiscal", "MTSDS133FMS", "sum12", "$tn", 2, +1),
    ("outlook", "Factory managers' 6-month outlook (Philly Fed)", "Business & consumer surveys", "GAFDFSA066MSFRBPHI", "level", "index", 1, +1),
    ("capex_plans", "Companies' plans to invest (Philly Fed)", "Business & consumer surveys", "CEFDFSA066MSFRBPHI", "level", "index", 1, +1),
    ("capex_orders", "Orders for business equipment (core capex)", "Business & consumer surveys", "NEWORDER", "yoy", "% y/y", 1, +1),
    ("it_invest", "Investment in computers, software & data-center gear", "Business & consumer surveys", "A679RC1Q027SBEA", "yoy", "% y/y", 1, +1),
    ("sentiment", "Consumer sentiment (UMich)", "Business & consumer surveys", "UMCSENT", "level", "index", 1, +1),
    ("oil", "WTI crude oil", "Households & markets", "DCOILWTICO", "level", "$/bbl", 1, +1),
    ("gas", "Retail gasoline", "Households & markets", "GASREGW", "level", "$/gal", 2, +1),
    ("mortgage", "30-year mortgage rate", "Households & markets", "MORTGAGE30US", "level", "%", 2, 0),
    ("jgb10", "Japan 10Y yield", "Global rates", "IRLTLT01JPM156N", "level", "%", 2, +1),
    ("gilt10", "UK 10Y yield", "Global rates", "IRLTLT01GBM156N", "level", "%", 2, +1),
    ("bund10", "Germany 10Y yield", "Global rates", "IRLTLT01DEM156N", "level", "%", 2, +1),
]
GROUPS = ["Inflation", "Expectations", "Growth & jobs", "Business & consumer surveys", "Policy & fiscal", "Global rates", "Households & markets"]

# Typical days from observation date (FRED stamps monthly data on the 1st) to public release.
RELEASE_LAG = {"CPIAUCSL": 43, "CPILFESL": 43, "CUSR0000SACL1E": 43, "PCEPILFE": 58, "CES0500000003": 36,
               "PAYEMS": 36, "UNRATE": 36, "MICH": 28, "A191RL1Q225SBEA": 120, "MTSDS133FMS": 42,
               "IC4WSA": 6, "GASREGW": 1, "MORTGAGE30US": 1, "THREEFYTP10": 0,
               "GAFDFSA066MSFRBPHI": 20, "CEFDFSA066MSFRBPHI": 20, "NEWORDER": 57, "A679RC1Q027SBEA": 120, "UMCSENT": 28,
               "IRLTLT01JPM156N": 35, "IRLTLT01GBM156N": 35, "IRLTLT01DEM156N": 35}
QUARTERLY = {"A191RL1Q225SBEA", "A679RC1Q027SBEA"}
MONTHLY = {"CPIAUCSL", "CPILFESL", "CUSR0000SACL1E", "PCEPILFE", "CES0500000003", "PAYEMS", "UNRATE", "MICH",
           "MTSDS133FMS", "IRLTLT01JPM156N", "IRLTLT01GBM156N", "IRLTLT01DEM156N",
           "GAFDFSA066MSFRBPHI", "CEFDFSA066MSFRBPHI", "NEWORDER", "UMCSENT"}
# Smallest change worth calling a push on yields, in the indicator's own unit.
MATERIAL = {"index": 2, "%": 0.1, "% y/y": 0.1, "% saar": 0.5, "k/mo": 25, "k": 10, "$tn": 0.1, "$/bbl": 3, "$/gal": 0.1}


def _monthly_index(pts):
    return {(d.year, d.month): (d, v) for d, v in pts}


def _derive(kind: str, pts: list) -> list:
    if kind == "level":
        return pts
    if kind == "thousands":
        return [(d, v / 1000) for d, v in pts]
    idx = _monthly_index(pts)
    out = []
    for (y, m), (d, v) in sorted(idx.items()):
        def back(n):
            yy, mm = y, m - n
            while mm <= 0:
                mm += 12
                yy -= 1
            return idx.get((yy, mm))
        if kind == "yoy" and back(12):
            out.append((d, (v / back(12)[1] - 1) * 100))
        elif kind == "ann3m" and back(3):
            out.append((d, ((v / back(3)[1]) ** 4 - 1) * 100))
        elif kind == "diff3avg" and back(3):
            out.append((d, (v - back(3)[1]) / 3))
        elif kind == "sum12" and all(back(k) for k in range(1, 12)):
            total = v + sum(back(k)[1] for k in range(1, 12))
            out.append((d, -total / 1e6))  # MTS reports $mn, deficits negative
    return out


def _period(series_id: str, d: date) -> str:
    if series_id in QUARTERLY:
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    if series_id in MONTHLY:
        return f"{d:%b} {d.year}"
    return f"{d:%b} {d.day}, {d.year}"


def _known_on(series_id: str, pts: list, when: date):
    lag = RELEASE_LAG.get(series_id, 1)
    best = None
    for d, v in pts:
        if d + timedelta(days=lag) <= when:
            best = (d, v)
    return best


def _fetch_all(start: date) -> dict:
    ids = sorted({x[3] for x in INDICATORS})
    with ThreadPoolExecutor(6) as ex:
        res = dict(zip(ids, ex.map(lambda i: _try(S.fred, i, start), ids)))
    return res


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def scorecard(past: date, asof: date) -> dict:
    """Indicator values as known at the start of the window and today, with the push each change exerts on yields."""
    start = date(past.year - 2, 1, 1)
    raw = _fetch_all(start)
    today = date.today()
    rows = []
    for key, label, group, sid, kind, unit, dec, push in INDICATORS:
        pts = raw.get(sid)
        if not pts:
            continue
        der = _derive(kind, pts)
        # Start of window: only what had been released by then. Now: the latest published reading.
        then, now = _known_on(sid, der, past), (der[-1] if der else None)
        if not now:
            continue
        chg = round(now[1] - then[1], dec + 1) if then else None
        material = chg is not None and abs(chg) >= MATERIAL.get(unit, 0.1)
        direction = (1 if chg > 0 else -1) * push if material and push else 0
        rows.append({
            "key": key, "label": label, "group": group, "series": sid, "unit": unit, "decimals": dec,
            "then": {"value": round(then[1], dec + 1), "period": _period(sid, then[0])} if then else None,
            "now": {"value": round(now[1], dec + 1), "period": _period(sid, now[0])},
            "change": chg, "push": "up" if direction > 0 else "down" if direction < 0 else "flat",
            "consequence": push == 0,
        })
    return {"rows": rows, "groups": GROUPS, "by_key": {r["key"]: r for r in rows}}


def fed_moves(past: date, asof: date) -> list:
    """Changes to the fed funds target (upper bound) inside the window: [(date, bp)]."""
    pts = _try(S.fred, "DFEDTARU", past - timedelta(days=10)) or []
    out, prev = [], None
    for d, v in pts:
        if prev is not None and v != prev and past < d <= asof:
            out.append((d, round((v - prev) * 100)))
        prev = v
    return out


def term_premium(past: date, asof: date):
    """Kim-Wright 10Y term premium at the window start and end (or None when the model data is too stale)."""
    pts = _try(S.fred, "THREEFYTP10", past - timedelta(days=30))
    if not pts:
        return None
    start = [p for p in pts if p[0] <= past]
    end = [p for p in pts if p[0] <= asof]
    if not start or not end:
        return None
    (d0, v0), (d1, v1) = start[-1], end[-1]
    if (past - d0).days > 5 or d1 <= past:
        return None  # model data lags the curve; too stale for this window
    return {"then": v0, "now": v1, "then_date": d0.isoformat(), "now_date": d1.isoformat(),
            "chg_bp": round((v1 - v0) * 100, 1), "stale_days": (asof - d1).days}
