"""Curve regime classification, news tagging, Fed-path math and auction metrics."""
from __future__ import annotations

import calendar
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import macro as M
import desk as Dk
import report as Rp
import narrative as N
import tape as TP
import secular as X
import sources as S
import story as St


def _safe(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except Exception:
        return None


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _bp(a, b):
    return round((a - b) * 100, 1) if a is not None and b is not None else None



# ---------------------------------------------------------------------------
# Curve
# ---------------------------------------------------------------------------
HORIZONS = {"1D": "1 day", "1W": "1 week", "1M": "1 month", "3M": "3 months", "1Y": "1 year"}
SPREADS = [("2s10s", "2Y", "10Y"), ("3m10y", "3M", "10Y"), ("2s5s", "2Y", "5Y"),
           ("5s30s", "5Y", "30Y"), ("10s30s", "10Y", "30Y")]

REGIME_TEXT = {
    "Bear steepener": "Long-dated yields rose more than short-dated ones. Investors are demanding more "
        "compensation to hold duration (a higher term premium). That usually traces to Treasury supply and "
        "deficit worries, firmer inflation expectations or stronger growth, rather than a change in the Fed path.",
    "Bull steepener": "Short-dated yields fell more than long-dated ones. The front end is pulling forward Fed "
        "easing, which usually follows softer data, cooler inflation or dovish Fed communication.",
    "Bear flattener": "Short-dated yields rose more than long-dated ones. The market is pricing a more "
        "restrictive Fed (fewer cuts or more hikes). The long end rose less because tighter policy is expected "
        "to cool growth and inflation later.",
    "Bull flattener": "Long-dated yields fell more than short-dated ones. This points to growth or inflation "
        "worries, safe-haven demand or a lower term premium, with the Fed path broadly unchanged.",
    "Twist steepener": "The front end fell while the long end rose. Investors expect easier policy near term but "
        "want more term premium further out, which often reflects doubts about inflation control or fiscal discipline.",
    "Twist flattener": "The front end rose while the long end fell: a hawkish Fed repricing that the long end "
        "reads as negative for growth.",
    "Parallel bear shift": "Yields rose by similar amounts across the curve: a broad repricing of rates rather "
        "than a change in curve shape.",
    "Parallel bull shift": "Yields fell by similar amounts across the curve: a broad rally rather than a change "
        "in curve shape.",
    "Little changed": "The curve barely moved over this window.",
}

REGIME_OUTLOOK = {
    "Bear steepener": "Duration stays under pressure while term premium rebuilds. Watch long-end auction tails "
        "(10Y, 20Y, 30Y), refunding-size guidance and deficit headlines. Steepeners (2s10s, 5s30s) tend to work "
        "in this regime, and mortgage and corporate borrowing costs rise with the long end.",
    "Bull steepener": "Consistent with an easing cycle being priced. Front-end duration usually outperforms. "
        "Bull steepening after an inversion has often come just before or during an economic slowdown.",
    "Bear flattener": "Tighter policy is being priced. The risk is policy overshoot: if the front end keeps "
        "leading, watch for re-inversion as a late-cycle signal. Flatteners and front-end shorts tend to work.",
    "Bull flattener": "A risk-off or disinflation signal: long duration rallies as growth expectations fade. If it "
        "persists alongside weak data, the market will pull forward cuts and the move can turn into a bull steepener.",
    "Twist steepener": "Mixed signal: near-term policy is expected to ease while long-end compensation rises. "
        "Persistent twist steepening is a classic sign of credibility or fiscal stress; watch long-end supply and "
        "inflation expectations.",
    "Twist flattener": "Hawkish front end with a growth-pessimistic long end, a late-cycle pattern. If the long end "
        "keeps falling, the market is pricing recession risk.",
    "Parallel bear shift": "A level-driven selloff. The next leg depends on whether the catalyst is policy (front "
        "end leads) or supply and inflation (long end leads).",
    "Parallel bull shift": "A level-driven rally. If data keep softening, expect the front end to take the lead.",
    "Little changed": "No clear signal from the curve over this window.",
}

# How each regime usually maps to drivers, before looking at the news.


def classify(d_short, d_long, threshold: float = 2.0) -> str:
    """Name the move of a curve segment from the bp changes at its short and long ends."""
    if d_short is None or d_long is None:
        return "n/a"
    slope, level = d_long - d_short, (d_short + d_long) / 2
    if abs(slope) < threshold:
        if abs(level) < threshold:
            return "Little changed"
        return "Parallel bear shift" if level > 0 else "Parallel bull shift"
    if d_short * d_long < 0 and min(abs(d_short), abs(d_long)) >= 1:
        return "Twist steepener" if slope > 0 else "Twist flattener"
    return f"{'Bear' if level > 0 else 'Bull'} {'steepener' if slope > 0 else 'flattener'}"


def _minus_months(d: date, n: int) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def load_curves(extra_years=()):
    today = date.today()
    years = {today.year, today.year - 1, *extra_years}
    nom = S.curve_series(years)
    real = _safe(S.curve_series, years, True) or {}
    return nom, real, max(nom)


def _spread(c, a, b):
    return _bp(c.get(b), c.get(a)) if c else None



NON_US_RX = re.compile(r"philippin|indonesia|\bindia|\brbi\b|\becb\b|bank of (england|japan|canada|korea)|\bboj\b"
                       r"|\bboe\b|\brba\b|australia|new zealand|south africa|turkey|turkish|brazil|mexico|\bpeso"
                       r"|rupee|nigeria|kenya|pakistan|malaysia|thailand|vietnam|pboc|riksbank|norges|\bsnb\b", re.I)
US_RX = re.compile(r"\bus\b|u\.s\.|\bfed\b|federal reserve|treasur|wall street|america|powell|fomc|washington", re.I)


def us_relevant(title: str) -> bool:
    return not NON_US_RX.search(title) or bool(US_RX.search(title))



# ---------------------------------------------------------------------------
# Curve analysis for one horizon
# ---------------------------------------------------------------------------
def _resolve_past(horizon: str, asof: date, series: dict):
    if horizon == "1D":
        earlier = [k for k in series if k < asof]
        return max(earlier) if earlier else None
    target = {"1W": asof - timedelta(days=7), "1M": _minus_months(asof, 1),
              "3M": _minus_months(asof, 3), "1Y": _minus_months(asof, 12)}.get(horizon)
    if target is None:
        target = date.fromisoformat(horizon)
    return S.on_or_before(series, target)[0]


def _d(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def _moved(x):
    return f"rose {x:.0f}bp" if x >= 0.5 else f"fell {abs(x):.0f}bp" if x <= -0.5 else "was unchanged"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"




def attribution(nom, real, asof, past) -> dict:
    """Split the 10Y move two ways: expected policy path vs term premium (Kim-Wright), and real vs breakeven (TIPS)."""
    tc, pc = nom[asof], nom[past]
    out = {"n10_bp": _bp(tc.get("10Y"), pc.get("10Y")), "tp_note": "", "path_bp": None, "tp_bp": None}
    tpw = M.term_premium(past, asof)
    if tpw:
        d0, d1 = date.fromisoformat(tpw["then_date"]), date.fromisoformat(tpw["now_date"])
        c0, c1 = S.on_or_before(nom, d0)[1], S.on_or_before(nom, d1)[1]
        n10 = _bp(c1["10Y"], c0["10Y"])
        out.update(n10_bp=n10, tp_bp=tpw["chg_bp"], path_bp=round(n10 - tpw["chg_bp"], 1), tp=tpw,
                   tp_note="" if (asof - d1).days <= 1 else f" through {_d(d1)} (latest model reading)")
    rd, rt = S.on_or_before(real, asof) if real else (None, None)
    _, rp = S.on_or_before(real, past) if real else (None, None)
    out["real_asof"] = rd.isoformat() if rd else None
    for t in ("5Y", "10Y", "30Y"):
        if rt and rp and t in rt and t in rp and tc.get(t) and pc.get(t):
            n_chg, r_chg = _bp(tc[t], pc[t]), _bp(rt[t], rp[t])
            out[t] = {"nominal": tc[t], "real": rt[t], "breakeven": round(tc[t] - rt[t], 2),
                      "nominal_chg": n_chg, "real_chg": r_chg, "breakeven_chg": round(n_chg - r_chg, 1)}
    if "10Y" in out:
        out["real_bp"], out["be_bp"] = out["10Y"]["real_chg"], out["10Y"]["breakeven_chg"]
    if "5Y" in out:
        out["be5_bp"] = out["5Y"]["breakeven_chg"]
    return out


def lead_driver(at) -> str:
    """Which half of the 10Y move was bigger: real yields (growth and the Fed) or inflation expectations (TIPS split)."""
    if at.get("real_bp") is not None:
        r, b = abs(at["real_bp"]), abs(at["be_bp"])
        if r + b and 0.35 <= r / (r + b) <= 0.65:
            return "Growth and inflation together"
        return "Growth and the Fed (real yields)" if r >= b else "Inflation expectations"
    return "n/a"


def curve_analysis(horizon: str) -> dict:
    extra = ()
    if horizon not in HORIZONS:
        t = date.fromisoformat(horizon)
        extra = (t.year, t.year - 1)
    nom, real, asof = load_curves(extra)
    past = _resolve_past(horizon, asof, nom)
    if past is None:
        raise ValueError("No Treasury curve data on or before that date.")
    if past >= asof:
        raise ValueError(f"Pick a date before the latest curve date ({asof.isoformat()}).")
    tc, pc = nom[asof], nom[past]
    tenors = [{"tenor": t, "years": y, "today": tc.get(t), "past": pc.get(t), "chg_bp": _bp(tc.get(t), pc.get(t))}
              for t, y in S.TENORS]
    chg = {r["tenor"]: r["chg_bp"] for r in tenors}
    spreads = {n: {"today": _spread(tc, a, b), "past": _spread(pc, a, b)} for n, a, b in SPREADS}
    for v in spreads.values():
        v["chg"] = round(v["today"] - v["past"], 1) if None not in (v["today"], v["past"]) else None
    regime = classify(chg.get("2Y"), chg.get("10Y"))
    segments = {"Front end (3M-2Y)": classify(chg.get("3M"), chg.get("2Y")),
                "Belly (2Y-5Y)": classify(chg.get("2Y"), chg.get("5Y")),
                "2s10s": regime,
                "Long end (10Y-30Y)": classify(chg.get("10Y"), chg.get("30Y"))}
    at = attribution(nom, real, asof, past)
    return {"horizon": horizon, "label": HORIZONS.get(horizon, f"since {_d(past)}"),
            "asof": asof.isoformat(), "past": past.isoformat(), "tenors": tenors, "spreads": spreads,
            "regime": regime, "regime_text": REGIME_TEXT.get(regime, ""), "segments": segments,
            "attribution": at, "lead": lead_driver(at), "implications": implications(regime, tc, pc, nom, asof)}


def implications(regime, tc, pc, nom, asof) -> list:
    out = [REGIME_OUTLOOK.get(regime, "")]
    m10, m10p = _spread(tc, "3M", "10Y"), _spread(pc, "3M", "10Y")
    if m10 is not None:
        if m10 < 0:
            out.append(f"3m10y is inverted at {m10:+.0f}bp, the classic recession signal.")
        elif m10p is not None and m10p < 0:
            out.append(f"3m10y has un-inverted to {m10:+.0f}bp; recessions have often begun after the re-steepening.")
    yr = [v["10Y"] for d, v in nom.items() if d > asof - timedelta(days=365) and "10Y" in v]
    if yr and tc.get("10Y") is not None:
        lo, hi = min(yr), max(yr)
        pct = (tc["10Y"] - lo) / (hi - lo) * 100 if hi > lo else 50
        out.append(f"The 10Y at {tc['10Y']:.2f}% sits at the {_ordinal(round(pct))} percentile of its 1-year range ({lo:.2f}% to {hi:.2f}%).")
    return [x for x in out if x]


def matrix() -> list:
    """Every preset window on one screen: tenor moves, regime and attribution. No news, so it is fast."""
    def row(h):
        try:
            a = curve_analysis(h)
            at = a["attribution"]
            return {"horizon": h, "label": a["label"], "past": a["past"], "regime": a["regime"],
                    "chg": {t["tenor"]: t["chg_bp"] for t in a["tenors"]},
                    "s2s10s": a["spreads"]["2s10s"]["chg"], "s5s30s": a["spreads"]["5s30s"]["chg"],
                    "real_bp": at.get("real_bp"),
                    "be_bp": at.get("be_bp"), "lead": a["lead"]}
        except Exception as e:
            return {"horizon": h, "error": str(e)}
    with ThreadPoolExecutor(5) as ex:
        return list(ex.map(row, HORIZONS))


def strip() -> dict:
    """Top-of-page market strip: levels and 1-day changes a desk glances at first."""
    a = curve_analysis("1D")
    lv = {t["tenor"]: t for t in a["tenors"]}
    at = a["attribution"]
    out = {"asof": a["asof"], "tenors": [{"tenor": k, "level": lv[k]["today"], "chg": lv[k]["chg_bp"]}
                                         for k in ("3M", "2Y", "5Y", "10Y", "30Y")],
           "s2s10s": a["spreads"]["2s10s"], "s5s30s": a["spreads"]["5s30s"]}
    if "10Y" in at:
        out["real10"] = {"level": at["10Y"]["real"], "chg": at["10Y"]["real_chg"]}
        out["be10"] = {"level": at["10Y"]["breakeven"], "chg": at["10Y"]["breakeven_chg"]}
    so = _safe(S.sofr_history, 5)
    if so:
        out["sofr"] = {"rate": so[0]["rate"], "date": so[0]["date"], "chg": round((so[0]["rate"] - so[1]["rate"]) * 100) if len(so) > 1 else None}
    out["move"] = move_index()
    fv = _safe(fed_cached)
    if fv:
        out["fed"] = {"lo": fv["target_lo"], "hi": fv["target_hi"], "effr": fv["effr"]}
        if fv["meetings"]:
            m = fv["meetings"][0]
            out["next"] = {"date": m["date"], "delta_bp": m["delta_bp"], "p_hike": m["p_hike"], "p_cut": m["p_cut"], "p_hold": m["p_hold"]}
        out["fed"]["effr_date"] = fv["effr_date"]
    return out


def _tag_items(items, theme_name):
    return [dict(i, theme=theme_name) for i in items if us_relevant(i["title"])]


def _near_path(past: date, asof: date, data) -> list:
    """Daily path for windows up to two years, from the Treasury par curve."""
    nom, _, _ = load_curves((past.year, past.year - 1))
    ff = S.cached("dfedtaru", 6 * 3600, lambda: S.fred("DFEDTARU", date(2008, 12, 1)))
    rows = []
    for d in sorted(x for x in nom if past <= x <= asof):
        v = nom[d]
        rs, ei, f = X.at(data["rstar"], d), X.at(data["einf"], d), X.at(ff, d)
        rows.append({"d": d.isoformat(), "y10": v.get("10Y"), "y2": v.get("2Y"), "ff": f and round(f[1] - 0.125, 3),
                     "anchor": round(rs[1] + ei[1], 2) if rs and ei else None, "rec": False,
                     "mp": X.mp_regime(d, data["ff"], data["walcl_yoy"], data["deficit"])})
    return rows


def _near_legs(rows):
    pts = [(date.fromisoformat(r["d"]), r["y10"]) for r in rows if r["y10"] is not None]
    if len(pts) < 2:
        return []
    piv = X.zigzag(pts, 0.20)
    return [{"from": a.isoformat(), "to": b.isoformat(), "y_from": round(va, 2), "y_to": round(vb, 2), "chg_bp": round((vb - va) * 100),
             "months": (b.year - a.year) * 12 + b.month - a.month, "mp": [],
             "history": [X._leg_label(a, b, X.load())]}
            for (a, va), (b, vb) in zip(piv, piv[1:])]


def _leg_news(legs, news):
    """Tag each turning point of a near window with the story verified outlets tied to rates most in those weeks."""
    names = {t["key"]: t["name"] for t in St.THEMES}
    for leg in legs:
        counts = {k: sum(1 for i in items if i.get("date") and leg["from"] <= i["date"] <= leg["to"])
                  for k, items in news["theme"].items()}
        if not counts:
            continue
        k, n = max(counts.items(), key=lambda kv: kv[1])
        if n < 2:
            continue
        focus = f"News focus: {N.lc(names[k])} ({n} verified stories)"
        h = leg["history"][0] if leg["history"] else ""
        leg["history"] = [focus if not h or h.startswith("No change") else f"{h}. {focus}"]


def story_view(horizon: str) -> dict:
    a = curve_analysis(horizon)
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    mode = X.mode_for(past, asof)
    with ThreadPoolExecutor(5) as ex:
        f_sc = ex.submit(M.scorecard, past, asof)
        f_news = ex.submit(St.gather, past, asof) if mode == "near" else None
        f_fed = ex.submit(_safe, fed_cached)
        f_auc = ex.submit(_safe, auctions_cached)
        f_tn = ex.submit(_safe, lambda: S.cached("tnews", 900, treasury_news))
        f_x = ex.submit(X.load)
        sc, fed, auc, tn, xd = f_sc.result(), f_fed.result(), f_auc.result(), f_tn.result(), f_x.result()
        news = f_news.result() if f_news else None
    if auc is not None and tn:
        auc = {**auc, "buybacks": tn.get("buybacks", [])}
    dec = X.decomposition(past, asof, xd)
    dc = S.cached(("debt_cycle", asof), 3600, lambda: X.debt_cycle(asof, xd))
    if mode == "near":
        pth = _near_path(past, asof, xd)
        lg = _near_legs(pth)
    else:
        pth = X.path(past, asof, xd)
        lg = X.legs(past, asof, mode, xd)
    watch = St.watch_list(fed, auc)

    moves = M.fed_moves(past, asof)
    themes = None
    if mode == "near":
        for k in news["theme"]:
            news["theme"][k] = [i for i in news["theme"][k] if us_relevant(i["title"])]
        at_ = a["attribution"]
        ch = {t["tenor"]: t["chg_bp"] for t in a["tenors"]}
        comps = {"d2": ch.get("2Y"), "d10": ch.get("10Y"), "d30": ch.get("30Y"), "real10": at_.get("real_bp"),
                 "be10": at_.get("be_bp"), "be5": at_.get("be5_bp"), "slope": (ch.get("30Y") or 0) - (ch.get("2Y") or 0)}
        themes = St.rank_themes(news, past, asof, sc, comps)
        _leg_news(lg, news)
    yh = St._yahoo_change(["SMH", "IGV", "GC=F", "^GSPC"], past)
    story = N.build(a, mode, sc, xd, moves, fed, watch, themes, yh, dc)
    with ThreadPoolExecutor(3) as ex:
        f_tr = ex.submit(TP.rates, a)
        f_x = ex.submit(lambda: _safe(TP.cross_asset, past, asof) or [])
        f_1y = ex.submit(lambda: _safe(curve_analysis, "1Y"))
        tr, cross, a1y = f_tr.result(), f_x.result(), f_1y.result()
    d10 = next(t["chg_bp"] for t in a["tenors"] if t["tenor"] == "10Y")
    rr = TP.regime_read(d10, tr["rows"], cross)
    story["exec"] = Dk.build(a, mode, tr, cross, rr, a1y and a1y["regime"], fed, sc["by_key"], moves, story["surveys"],
                             themes, TP.front_end(a, sc["by_key"]), story["episodes"])
    story["report"] = Rp.build(a, mode, tr, cross, rr, a1y and a1y["regime"], fed, sc["by_key"], moves, story["surveys"],
                               themes, story["episodes"], auc, dc, story["exec"]["horizon_name"])
    story["summary_exec"] = Rp.summary(a, mode, tr, cross, a1y and a1y["regime"], fed, sc["by_key"], moves, story["surveys"],
                                       themes, story["episodes"], auc, story["exec"]["horizon_name"])
    story["headline"] = story["summary_exec"]["headline"]
    if mode == "near":
        names = {t["key"]: t["name"] for t in St.THEMES}
        pool = _tag_items(news["rates"], "Rates")
        for t in story["themes"]:
            pool += _tag_items(news["theme"].get(t["key"], []), names[t["key"]])
        seen, inside, after = set(), [], []
        for i in sorted(pool, key=lambda x: x.get("published") or "", reverse=True):
            k = re.sub(r"\W+", "", i["title"].lower())[:90]
            if k in seen or not i.get("date"):
                continue
            seen.add(k)
            (after if i["date"] > a["asof"] else inside if i["date"] >= (past - timedelta(days=1)).isoformat() else []).append(i)
        headlines, since = inside[:30], after[:12]
    else:
        headlines, since = [], []
    events = [{"from": e["from"][:7], "to": e["to"][:7], "text": f"{e['title']}. {e['story']}", "title": e["title"],
               "data_only": bool(e.get("data_only"))} for e in story["episodes"]]
    return {"horizon": horizon, "mode": mode, "past": a["past"], "asof": a["asof"], "regime": a["regime"],
            "lead_label": a["lead"] if mode == "near" else story["story_name"], "story": {**story, "so_what": a["implications"]}, "scorecard": sc["rows"], "groups": sc["groups"],
            "headlines": headlines, "since": since, "events": events,
            "path": pth, "legs": lg, "decomposition": dec, "debt_cycle": dc}


def curve_history(days: int = 400) -> dict:
    nom, _, asof = load_curves()
    pts = sorted((d, v) for d, v in nom.items() if d > asof - timedelta(days=days))
    return {"dates": [d.isoformat() for d, _ in pts],
            "2Y": [v.get("2Y") for _, v in pts], "10Y": [v.get("10Y") for _, v in pts],
            "2s10s": [_spread(v, "2Y", "10Y") for _, v in pts],
            "3m10y": [_spread(v, "3M", "10Y") for _, v in pts]}


# ---------------------------------------------------------------------------
# Fed path from 30-day fed funds futures
# ---------------------------------------------------------------------------
def _months_from(d: date, n: int):
    y, m, out = d.year, d.month, []
    for _ in range(n):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def implied_path(prices: dict, spot: float, meetings: list, realized: dict | None = None) -> list:
    """CME-style chaining. prices: {(y, m): ZQ price}; realized: {meeting date: EFFR after it} for
    meetings already held (their contracts may have expired). Returns post-meeting implied EFFR per meeting."""
    meeting_months = {(date.fromisoformat(m["date"]).year, date.fromisoformat(m["date"]).month) for m in meetings}
    pre, out = spot, []
    for mt in meetings:
        d = date.fromisoformat(mt["date"])
        ym = (d.year, d.month)
        nxt = (d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1)
        n_days = calendar.monthrange(d.year, d.month)[1]
        frac = d.day / n_days  # days 1..d at the old rate; new rate effective the day after
        if realized and mt["date"] in realized:
            post = realized[mt["date"]]
        elif nxt not in meeting_months and nxt in prices:
            post = 100 - prices[nxt]
        elif ym in prices and frac < 1:
            post = ((100 - prices[ym]) - frac * pre) / (1 - frac)
        else:
            break
        out.append({**mt, "pre": round(pre, 4), "post": round(post, 4), "delta_bp": round((post - pre) * 100, 1)})
        pre = post
    return out


def _move_dist(delta_bp: float) -> dict:
    n = delta_bp / 25
    lo = math.floor(n)
    frac = n - lo
    dist = {lo * 25: 1 - frac}
    if frac > 1e-9:
        dist[(lo + 1) * 25] = frac
    return dist


def _convolve(a: dict, b: dict) -> dict:
    out = {}
    for ka, pa in a.items():
        for kb, pb in b.items():
            out[ka + kb] = out.get(ka + kb, 0) + pa * pb
    return out


def fed_view() -> dict:
    effr = S.effr_history(90)
    cur = effr[0]
    spot, lo, hi = cur["rate"], cur["lo"], cur["hi"]
    today = date.today()
    meetings_all = S.fomc_meetings()
    upcoming = [m for m in meetings_all
                if today <= date.fromisoformat(m["date"]) <= today + timedelta(days=365)]

    months = _months_from(today - timedelta(days=40), 16)
    spark = _safe(S.yahoo_spark, [S.zq_symbol(*ym) for ym in months]) or {}
    charts = {ym: spark.get(S.zq_symbol(*ym)) for ym in months}
    prices_now = {ym: c["price"] for ym, c in charts.items() if c and c.get("price")}
    path = implied_path(prices_now, spot, upcoming)

    # Meeting-by-meeting probabilities, chained into a distribution of the target range.
    cum = {0: 1.0}
    for p in path:
        dist = _move_dist(p["delta_bp"])
        cum = _convolve(cum, dist)
        p["p_hike"] = round(sum(v for k, v in dist.items() if k > 0), 3)
        p["p_cut"] = round(sum(v for k, v in dist.items() if k < 0), 3)
        p["p_hold"] = round(dist.get(0, 0), 3)
        p["cum_bp"] = round((p["post"] - spot) * 100, 1)
        ranges = sorted(cum.items())
        p["ranges"] = [{"range": f"{lo + k / 100:.2f}-{hi + k / 100:.2f}", "bp": k, "p": round(v, 3)}
                       for k, v in ranges if v >= 0.01]
        p["most_likely"] = max(p["ranges"], key=lambda r: r["p"]) if p["ranges"] else None

    # Same path as priced 1 week and 1 month ago.
    def effr_on(d):
        for r in effr:
            if date.fromisoformat(r["date"]) <= d:
                return r["rate"]
        return spot

    def prices_on(d):
        out = {}
        for ym, c in charts.items():
            if c and c["hist"]:
                pts = [px for dd, px in c["hist"] if dd <= d]
                if pts:
                    out[ym] = pts[-1]
        return out

    history = {}
    for key, back in (("1W", 7), ("1M", 30)):
        d = today - timedelta(days=back)
        mts = [m for m in meetings_all if date.fromisoformat(m["date"]) >= d]
        held = {m["date"]: effr_on(date.fromisoformat(m["date"]) + timedelta(days=2))
                for m in mts if date.fromisoformat(m["date"]) < today}
        old = {x["date"]: x["post"] for x in implied_path(prices_on(d), effr_on(d), mts, held)}
        history[key] = {"date": d.isoformat(), "post": old}
        for p in path:
            if p["date"] in old:
                p[f"shift_{key}_bp"] = round((p["post"] - old[p["date"]]) * 100, 1)

    monthly = [{"month": f"{y}-{m:02d}", "symbol": S.zq_symbol(y, m), "price": prices_now[(y, m)],
                "implied": round(100 - prices_now[(y, m)], 3)}
               for (y, m) in months if (y, m) in prices_now and (y, m) >= (today.year, today.month)]

    return {"effr": spot, "effr_date": cur["date"], "target_lo": lo, "target_hi": hi,
            "meetings": path, "upcoming_meetings": upcoming[:10], "monthly": monthly,
            "history": history, "effr_series": list(reversed(effr)),
            "futures_time": next((c["time"] for c in charts.values() if c and c.get("time")), None)}



def fed_cached():
    return S.cached("fed_view", 300, fed_view)


def auctions_cached():
    return S.cached("auctions_view", 600, auctions_view)


def fed_context(fv: dict) -> dict:
    """What the Fed is reacting to, and how pricing has shifted."""
    today = date.today()
    sc = M.scorecard(today - timedelta(days=365), today)
    k = sc["by_key"]
    pick = [k[x] for x in ("core_pce", "core_cpi_3m", "wages", "unrate", "payrolls", "mich", "fwd5y5y") if x in k]
    out = {"indicators": pick}
    if "core_pce" in k:
        out["real_policy_rate"] = round(fv["effr"] - k["core_pce"]["now"]["value"], 2)
    m = fv["meetings"]
    lines = []
    if m:
        nxt, last = m[0], m[-1]
        lines.append(f"{_d(date.fromisoformat(nxt['date']))} meeting: {St._fomc_phrase(nxt)}. The futures-implied move of "
                     f"{nxt['delta_bp']:+.1f}bp is that chance times 25bp, not a forecast of "
                     f"{'an' if str(round(abs(nxt['delta_bp']))).startswith(('8', '11', '18')) else 'a'} {abs(nxt['delta_bp']):.0f}bp move.")
        lines.append(f"By the {_d(date.fromisoformat(last['date']))} meeting: {last['cum_bp']:+.0f}bp in total "
                     f"(about {abs(last['cum_bp']) / 25:.1f} quarter-point moves), taking EFFR from {fv['effr']:.2f}% to {last['post']:.2f}%.")
        for key, lab in (("1W", "week"), ("1M", "month")):
            w = last.get(f"shift_{key}_bp")
            if w is not None:
                lines.append(f"Since {_d(date.fromisoformat(fv['history'][key]['date']))} that end-point moved {w:+.0f}bp "
                             f"({'more hikes priced' if w > 2 else 'fewer hikes priced' if w < -2 else 'little changed'}).")
    if "real_policy_rate" in out:
        r = out["real_policy_rate"]
        pce = k["core_pce"]["now"]
        lines.append(f"Real policy rate: EFFR {fv['effr']:.2f}% ({_d(date.fromisoformat(fv['effr_date']))}) minus core PCE "
                     f"{pce['value']:.1f}% ({pce['period']}) = {r:+.2f}%, "
                     f"{'restrictive' if r > 1 else 'mildly restrictive' if r > 0.25 else 'near neutral or loose'}.")
    out["summary"] = lines
    items = [i for i in (_safe(S.google_news, '(Fed OR FOMC OR "Federal Reserve") (rates OR "rate cut" OR "rate hike" OR inflation)', when="7d") or [])
             if us_relevant(i["title"])]
    out["news"] = items[:12]
    out["speeches"] = _safe(S.rss, S.FED_SPEECH_RSS, 8) or []
    out["press"] = _safe(S.rss, S.FED_PRESS_RSS, 8) or []
    return out


# ---------------------------------------------------------------------------
# Auctions
# ---------------------------------------------------------------------------
def _key(x):
    bill = x.get("securityType") == "Bill"
    return (x.get("securityType"), x.get("securityTerm") if bill else (x.get("term") or x.get("securityTerm")),
            x.get("tips") == "Yes", x.get("floatingRate") == "Yes", x.get("cashManagementBillCMB") == "Yes")


def _label(x):
    kind = "TIPS" if x.get("tips") == "Yes" else "FRN" if x.get("floatingRate") == "Yes" else x.get("securityType")
    if x.get("cashManagementBillCMB") == "Yes":
        kind = "CMB"
    term = x.get("securityTerm")
    orig = x.get("term") or x.get("originalSecurityTerm")
    if x.get("securityType") != "Bill" and orig and orig != term:
        return f"{orig} {kind} (reopening, {term})"
    return f"{term} {kind}"


def _has_results(x):
    return any(x.get(k) for k in ("highYield", "highDiscountRate", "highDiscountMargin"))


def auction_metrics(x) -> dict:
    bill = x.get("securityType") == "Bill"
    frn = x.get("floatingRate") == "Yes"
    pd_, di, ind = (_f(x.get("primaryDealerAccepted")) or 0, _f(x.get("directBidderAccepted")) or 0,
                    _f(x.get("indirectBidderAccepted")) or 0)
    comp = pd_ + di + ind
    if frn:
        stop, med, low, kind = (_f(x.get("highDiscountMargin")), _f(x.get("averageMedianDiscountMargin")),
                                _f(x.get("lowDiscountMargin")), "discount margin")
    elif bill:
        stop, med, low, kind = (_f(x.get("highDiscountRate")), _f(x.get("averageMedianDiscountRate")),
                                _f(x.get("lowDiscountRate")), "discount rate")
    else:
        stop, med, low, kind = (_f(x.get("highYield")), _f(x.get("averageMedianYield")),
                                _f(x.get("lowYield")), "real yield" if x.get("tips") == "Yes" else "yield")
    year = (x.get("auctionDate") or "")[:4]
    return {
        "auction_date": (x.get("auctionDate") or "")[:10], "cusip": x.get("cusip"), "isin": isin(x.get("cusip")), "security": _label(x),
        "reopening": x.get("reopening") == "Yes", "offering_bn": (_f(x.get("offeringAmount")) or 0) / 1e9 or None,
        "tendered_bn": (_f(x.get("totalTendered")) or 0) / 1e9 or None,
        "accepted_bn": (_f(x.get("totalAccepted")) or 0) / 1e9 or None,
        "btc": _f(x.get("bidToCoverRatio")), "stop": stop, "median": med, "low": low, "stop_kind": kind,
        "investment_rate": _f(x.get("highInvestmentRate")), "coupon": _f(x.get("interestRate")),
        "indirect_pct": round(ind / comp * 100, 1) if comp else None,
        "direct_pct": round(di / comp * 100, 1) if comp else None,
        "dealer_pct": round(pd_ / comp * 100, 1) if comp else None,
        "soma_bn": (_f(x.get("somaAccepted")) or 0) / 1e9 or None,
        "allotted_at_high_pct": _f(x.get("allocationPercentage")),
        "results_pdf": S.td_pdf(year, x.get("pdfFilenameCompetitiveResults")),
    }


def _avg(xs):
    xs = [v for v in xs if v is not None]
    return round(sum(xs) / len(xs), 2) if xs else None



PAR_TENOR = {"2-Year": "2Y", "3-Year": "3Y", "5-Year": "5Y", "7-Year": "7Y", "10-Year": "10Y", "20-Year": "20Y",
             "30-Year": "30Y", "4-Week": "1M", "6-Week": "1.5M", "8-Week": "2M", "13-Week": "3M", "17-Week": "4M",
             "26-Week": "6M", "52-Week": "1Y"}


TAIL_BP = 2.0  # about one standard deviation of the market-adjusted gap across last year's coupon auctions


def isin(cusip):
    """US ISIN from a 9-character CUSIP: 'US' + CUSIP + ISO 6166 check digit (Luhn over the digit expansion)."""
    if not cusip or len(cusip) != 9:
        return None
    body = "US" + cusip.upper()
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return body + str((10 - total % 10) % 10)


def _market_gap(x, m, nom, real):
    """The auction's rate minus the same maturity's par yield at that day's close (bp).

    The true measure of an auction against expectations is the tail: the stop versus the when-issued yield at the
    1pm bid deadline. When-issued prices are not free, so the same-day closing par yield stands in for them."""
    if x.get("floatingRate") == "Yes":
        return None
    bill = x.get("securityType") == "Bill"
    term = x.get("securityTerm") if bill else (x.get("term") or x.get("securityTerm"))
    tenor = PAR_TENOR.get(term)
    src = real if x.get("tips") == "Yes" else nom
    d = date.fromisoformat(m["auction_date"]) if m.get("auction_date") else None
    if not tenor or not src or d not in src or src[d].get(tenor) is None:
        return None
    rate = m["investment_rate"] if bill else m["stop"]
    if rate is None:
        return None
    par = src[d][tenor]
    return {"rate": rate, "rate_kind": "investment rate" if bill else "high yield", "par": par,
            "par_label": f"{tenor} {'TIPS real' if x.get('tips') == 'Yes' else 'par'} yield", "date": d.isoformat(),
            "gap_bp": round((rate - par) * 100, 1)}


def _quality(m, hist):
    """Strong / In line / Soft, judged against the market.

    gap = auction rate minus the same-day closing yield for that maturity. The fitted curve sits a little off any
    single issue, so the read is the gap minus that security's usual gap over its prior six auctions:
    +2bp or more = priced cheaper than the market expected (Soft); -2bp or less = stopped through (Strong).
    Without curve data it falls back to demand: bid-to-cover, dealer take-down and indirect share vs the prior six."""
    prev = [h for h in hist if h["btc"] is not None][:6]
    if not prev or m["btc"] is None:
        return None, {}
    avg = {"btc": _avg([h["btc"] for h in prev]), "dealer": _avg([h["dealer_pct"] for h in prev]),
           "indirect": _avg([h["indirect_pct"] for h in prev]), "n": len(prev),
           "prior": [{"date": h["auction_date"], "btc": h["btc"], "dealer": h["dealer_pct"], "indirect": h["indirect_pct"],
                      "gap": (h.get("mkt") or {}).get("gap_bp")} for h in prev]}
    gaps = [h["mkt"]["gap_bp"] for h in prev if h.get("mkt")]
    if m.get("mkt") and len(gaps) >= 3:
        usual = sum(gaps) / len(gaps)
        tail = m["mkt"]["gap_bp"] - usual
        avg.update(basis="market", mkt=m["mkt"], usual_gap=round(usual, 1), n_gap=len(gaps), tail_bp=round(tail, 1),
                   threshold=TAIL_BP)
        return ("Soft" if tail >= TAIL_BP else "Strong" if tail <= -TAIL_BP else "In line"), avg
    score = (m["btc"] - avg["btc"]) / 0.1
    if m["dealer_pct"] is not None and avg["dealer"] is not None:
        score += (avg["dealer"] - m["dealer_pct"]) / 3
    if m["indirect_pct"] is not None and avg["indirect"] is not None:
        score += (m["indirect_pct"] - avg["indirect"]) / 3
    avg.update(basis="demand", score=round(score, 1))
    return ("Strong" if score >= 1.5 else "Soft" if score <= -1.5 else "In line"), avg


def _group(x):
    if x.get("securityType") == "Bill":
        return "Bills"
    return "Bonds" if x.get("securityType") == "Bond" else "Notes"


def _comparable_rate(x, m):
    """The rate to compare with the secondary market: bond-equivalent (investment) rate for bills, yield otherwise."""
    if x.get("securityType") == "Bill":
        return m["investment_rate"]
    return m["stop"]


def _takeaway(u):
    """One plain-English line a trader would say about the setup."""
    l, out = u["last"], []
    if not l:
        return "No equivalent auction in the past year to compare with."
    if u["now_vs_last_bp"] is not None:
        d = u["now_vs_last_bp"]
        if abs(d) < 3:
            out.append(f"Trades in line with the last auction ({d:+.0f}bp).")
        else:
            out.append(f"Trades {abs(d):.0f}bp {'above' if d > 0 else 'below'} the last auction's rate, so it should price "
                       f"{'cheaper (higher yield)' if d > 0 else 'richer (lower yield)'} than on {_d(date.fromisoformat(l['auction_date']))}.")
    if u["offering_bn"] and l["offering_bn"]:
        ds = u["offering_bn"] - l["offering_bn"]
        out.append("Size unchanged." if abs(ds) < 0.5 else f"Size {'up' if ds > 0 else 'down'} ${abs(ds):.0f}bn vs last time.")
    elif not u["offering_bn"]:
        out.append(f"Size to be announced {_d(date.fromisoformat(u['announcement_date']))}.")
    q, avg = u["last_quality"], u["last_avg"]
    if q and avg and avg.get("basis") == "market":
        t = avg["tail_bp"]
        out.append(f"Last time it priced {abs(t):.1f}bp {'cheaper' if t > 0 else 'richer'} than the market expected "
                   f"({q.lower()}); bid-to-cover {l['btc']:.2f} vs {avg['btc']:.2f} average.")
    elif q and avg:
        out.append(f"Last time demand was {q.lower()}: bid-to-cover {l['btc']:.2f} vs {avg['btc']:.2f} average, "
                   f"dealers left with {l['dealer_pct']:.0f}% vs {avg['dealer']:.0f}%.")
        if q == "Soft" and (u["now_vs_last_bp"] or 0) > 5:
            out.append("Watch for another soft result: demand was below its recent average last time, and the new auction comes at a higher yield.")
        elif q == "Strong" and (u["now_vs_last_bp"] or 0) > 5:
            out.append("A higher yield plus strong demand last time points to a well-received auction.")
    return " ".join(out)


def _par_duration(y_pct, years):
    """Modified duration of a par bond."""
    if not y_pct or years <= 0:
        return 0.0
    y, n = y_pct / 100, max(1, round(years * 2))
    return (1 / y) * (1 - 1 / (1 + y / 2) ** n)


def supply_metrics(upcoming, rows, done, by_key, tc, asof, metrics=None) -> dict:
    """The four supply numbers desks watch: net new cash, duration supply, bill share of debt, coupon demand trend."""
    out = {}
    # 1. Net new cash: announced offerings minus the maturing amount on each settlement date (per security type).
    groups = {}
    for u in upcoming:
        off, mat = _f(u.get("offeringAmount")), _f(u.get("estimatedAmountOfPubliclyHeldMaturingSecuritiesByType"))
        if not off or mat is None:
            continue
        g = groups.setdefault(((u.get("issueDate") or "")[:10], u.get("securityType")), {"offer": 0.0, "mature": mat, "n": 0})
        g["offer"] += off; g["n"] += 1
    if groups:
        offer = sum(g["offer"] for g in groups.values()) / 1e9
        mature = sum(g["mature"] for g in groups.values()) / 1e9
        out["net_cash"] = {"net_bn": round(offer - mature, 1), "gross_bn": round(offer, 1), "maturing_bn": round(mature, 1),
                           "settle": sorted({k[0] for k in groups}), "auctions": sum(g["n"] for g in groups.values()),
                           "unsized": sum(1 for u in upcoming if not _f(u.get("offeringAmount")))}
    # 2. Duration supply: coupon auctions ahead in 10-year equivalents (size x duration / 10Y duration).
    d10 = _par_duration(tc.get("10Y"), 10)
    eq, est, parts = 0.0, 0, []
    for r in rows:
        if r["type"] == "Bill" or r["frn"]:
            continue
        m = re.match(r"(\d+)-Year", r["security"])
        if not m or not d10:
            continue
        yrs = int(m.group(1))
        size = r["offering_bn"] or (r["last"]["offering_bn"] if r["last"] else None)
        if not size:
            continue
        est += 0 if r["offering_bn"] else 1
        y = (r["secondary"] if not r["tips"] else tc.get(f"{yrs}Y")) or tc.get(f"{yrs}Y")
        dur = _par_duration(y, yrs)
        e = size * dur / d10
        eq += e
        parts.append({"security": r["security"].split(" (")[0], "size_bn": size, "estimated": not r["offering_bn"],
                      "eq10_bn": round(e, 1), "dur": round(dur, 2), "yield": y})
    if parts:
        out["duration"] = {"eq10_bn": round(eq, 1), "estimated": est, "parts": parts, "d10": round(d10, 2), "y10": tc.get("10Y")}
    # 3. Bills as a share of marketable debt (MSPD), now and a year earlier.
    comp = _safe(S.debt_composition, 14) or []
    if comp:
        now = comp[0]
        yr = next((c for c in comp if c["date"] <= (date.fromisoformat(now["date"]) - timedelta(days=360)).isoformat()), None)
        out["bill_share"] = {"pct": round(now["bills"] / now["total"] * 100, 1), "date": now["date"],
                             "bills_tn": round(now["bills"] / 1e6, 2), "total_tn": round(now["total"] / 1e6, 2),
                             "pct_1y": round(yr["bills"] / yr["total"] * 100, 1) if yr else None, "date_1y": yr["date"] if yr else None}
    # 4. Coupon demand trend: last 10 coupon auctions vs the 10 before.
    coupons = [x for x in done if x.get("securityType") != "Bill" and x.get("floatingRate") != "Yes"]
    if len(coupons) >= 12:
        def stats(xs):
            ms = [auction_metrics(x) for x in xs]
            return {"dealer": _avg([m["dealer_pct"] for m in ms]), "indirect": _avg([m["indirect_pct"] for m in ms]),
                    "btc": _avg([m["btc"] for m in ms]), "from": ms[-1]["auction_date"], "to": ms[0]["auction_date"]}
        last10, prev10 = coupons[:10], coupons[10:20]
        reads = []
        for x in last10:
            m = metrics(x)
            older = [metrics(h) for h in by_key.get(_key(x), []) if h["auctionDate"] < x["auctionDate"]][:6]
            q, avg = _quality(m, older)
            reads.append({"date": m["auction_date"], "security": m["security"].split(" (")[0], "quality": q,
                          "basis": avg.get("basis"), "gap": (m.get("mkt") or {}).get("gap_bp"), "usual": avg.get("usual_gap"),
                          "tail": avg.get("tail_bp"), "score": avg.get("score")})
        qs = [r["quality"] for r in reads]
        out["demand"] = {"last10": stats(last10), "prev10": stats(prev10), "reads": reads, "threshold": TAIL_BP,
                         "strong": qs.count("Strong"), "soft": qs.count("Soft"), "in_line": qs.count("In line")}
    return out


def auctions_view() -> dict:
    today = date.today()
    upcoming = S.td_upcoming()
    done = [x for x in S.td_auctioned() if _has_results(x) and (x.get("auctionDate") or "")[:10] <= today.isoformat()]
    done.sort(key=lambda x: x["auctionDate"], reverse=True)
    by_key = {}
    for x in done:
        by_key.setdefault(_key(x), []).append(x)
    nom, real, asof = load_curves()
    tc = nom[asof]
    rd, rt = S.on_or_before(real, asof) if real else (None, None)
    memo = {}

    def metrics(x):
        k = (x.get("cusip"), x.get("auctionDate"))
        if k not in memo:
            m = auction_metrics(x)
            m["mkt"] = _market_gap(x, m, nom, real)
            memo[k] = m
        return memo[k]

    def secondary(x):
        if x.get("floatingRate") == "Yes":
            return None, None
        term = x.get("securityTerm") if x.get("securityType") == "Bill" else (x.get("term") or x.get("securityTerm"))
        tenor = PAR_TENOR.get(term)
        if x.get("tips") == "Yes":
            return (rt or {}).get(tenor), "TIPS real yield"
        return tc.get(tenor), f"{tenor} par yield" if tenor else None

    rows = []
    for u in sorted(upcoming, key=lambda x: (x["auctionDate"], x.get("securityTerm"))):
        hist = [metrics(h) for h in by_key.get(_key(u), [])[:8]]
        last = hist[0] if hist else None
        q, avg = _quality(last, hist[1:]) if last else (None, {})
        sec, sec_label = secondary(u)
        comp = _comparable_rate(u, last) if last else None
        announced = (u.get("announcementDate") or "")[:10] <= today.isoformat() and bool(u.get("offeringAmount"))
        row = {
            "auction_date": u["auctionDate"][:10], "security": _label(u), "group": _group(u), "type": u.get("securityType"),
            "tips": u.get("tips") == "Yes", "frn": u.get("floatingRate") == "Yes", "cusip": u.get("cusip") or None,
            "isin": isin(u.get("cusip")),
            "reopening": u.get("reopening") == "Yes", "announced": announced,
            "announcement_date": (u.get("announcementDate") or "")[:10],
            "offering_bn": (_f(u.get("offeringAmount")) or 0) / 1e9 or None,
            "issue_date": (u.get("issueDate") or "")[:10], "maturity_date": (u.get("maturityDate") or "")[:10],
            "closing_time": u.get("closingTimeCompetitive"),
            "announcement_pdf": S.td_pdf((u.get("announcementDate") or "")[:4], u.get("pdfFilenameAnnouncement")),
            "secondary": sec, "secondary_label": sec_label, "secondary_date": (rd if u.get("tips") == "Yes" and rd else asof).isoformat(),
            "last": last, "last_rate": comp, "last_quality": q, "last_avg": avg,
            "now_vs_last_bp": _bp(sec, comp) if sec is not None and comp is not None else None,
            "coupons_history": [{"date": h["auction_date"], "stop": h["stop"], "btc": h["btc"]} for h in reversed(hist)],
        }
        row["avg_btc"], row["avg_dealer"], row["avg_indirect"] = avg.get("btc"), avg.get("dealer"), avg.get("indirect")
        row["takeaway"] = _takeaway(row)
        rows.append(row)

    cutoff = (today - timedelta(days=45)).isoformat()
    results = []
    for x in done:
        if x["auctionDate"][:10] < cutoff or x.get("securityType") == "Bill":
            continue
        m = dict(metrics(x))
        older = [metrics(h) for h in by_key.get(_key(x), []) if h["auctionDate"] < x["auctionDate"]][:6]
        q, avg = _quality(m, older)
        m.update(quality=q, avg=avg, avg_btc=avg.get("btc"), avg_dealer=avg.get("dealer"), avg_indirect=avg.get("indirect"),
                 avg_n=avg.get("n"))
        results.append(m)
    groups = {g: [r for r in rows if r["group"] == g] for g in ("Bills", "Notes", "Bonds")}
    summary = {g: {"count": len(v), "sized_bn": sum(r["offering_bn"] or 0 for r in v),
                   "unsized": sum(1 for r in v if not r["offering_bn"]),
                   "first": v[0]["auction_date"] if v else None, "last": v[-1]["auction_date"] if v else None}
               for g, v in groups.items()}
    summary["last_result"] = results[0] if results else None
    summary["metrics"] = supply_metrics(upcoming, rows, done, by_key, tc, asof, metrics)
    return {"groups": groups, "upcoming": rows, "coupons": [r for r in rows if r["type"] != "Bill"],
            "recent_coupons": results, "summary": summary, "curve_date": asof.isoformat()}


def money_markets() -> dict:
    """Funding and liquidity conditions that decide whether the front end trades on policy or on liquidity."""
    today = date.today()
    out = {"items": [], "reading": []}
    sofr = _safe(S.sofr_history, 30) or []
    effr = _safe(S.effr_history, 30) or []
    iorb = _safe(S.fred, "IORB", today - timedelta(days=90)) or []
    rrp = _safe(S.fred, "RRPONTSYD", today - timedelta(days=90)) or []
    res = _safe(S.fred, "WRESBAL", today - timedelta(days=120)) or []
    tga = _safe(S.tga_history, 40) or []

    def month_ago(pts, key=None):
        cut = today - timedelta(days=30)
        older = [p for p in pts if (date.fromisoformat(p["date"]) if key else p[0]) <= cut]
        if not older:
            return None
        o = max(older, key=lambda p: p["date"] if key else p[0])
        return o[key] if key else o[1]

    def item(key, label, value, unit, dt, chg, meaning, src, dec=2):
        out["items"].append({"key": key, "label": label, "value": round(value, dec) if value is not None else None, "unit": unit,
                             "date": dt, "chg_1m": round(chg, dec) if chg is not None else None, "meaning": meaning, "src": src})

    if sofr:
        s0 = sofr[0]
        item("sofr", "SOFR", s0["rate"], "%", s0["date"], s0["rate"] - (month_ago(sofr, "rate") or s0["rate"]),
             f"Overnight Treasury repo rate; 1st–99th percentile {s0['p1']:.2f}–{s0['p99']:.2f}%, volume ${s0['volume_bn'] / 1000:.2f}tn.", "sofr")
    if effr:
        e0 = effr[0]
        item("effr", "Effective fed funds", e0["rate"], "%", e0["date"], e0["rate"] - (month_ago(effr, "rate") or e0["rate"]),
             f"Inside the {e0['lo']:.2f}–{e0['hi']:.2f}% target range.", "effr")
    if iorb:
        item("iorb", "Interest on reserve balances (IORB)", iorb[-1][1], "%", iorb[-1][0].isoformat(), None,
             "The rate the Fed pays on bank reserves; the effective ceiling for overnight rates when reserves are plentiful.", "fred:IORB")
    if sofr and iorb:
        sp = (sofr[0]["rate"] - iorb[-1][1]) * 100
        item("sofr_iorb", "SOFR minus IORB", sp, "bp", sofr[0]["date"], None,
             ("Repo above IORB: reserves are becoming scarce and banks pay up for cash." if sp > 0 else
              "Repo at or below IORB: reserves are still ample."), "sofr,fred:IORB", 0)
    if rrp:
        item("rrp", "Fed overnight reverse repo (ON RRP)", rrp[-1][1], "$bn", rrp[-1][0].isoformat(),
             rrp[-1][1] - (month_ago(rrp) or rrp[-1][1]),
             "Cash money funds park at the Fed. Near zero means the buffer is used up: QT or a TGA build now drains bank reserves directly.", "fred:RRPONTSYD", 1)
    if res:
        item("reserves", "Bank reserves at the Fed", res[-1][1] / 1e6, "$tn", res[-1][0].isoformat(),
             (res[-1][1] - (month_ago(res) or res[-1][1])) / 1e6, "The banking system's cash buffer; weekly.", "fred:WRESBAL", 2)
    if tga:
        item("tga", "Treasury General Account (TGA)", tga[0][1], "$bn", tga[0][0].isoformat(),
             tga[0][1] - (min((v for d, v in tga if d <= today - timedelta(days=30)), default=tga[0][1]) if False else
                          next((v for d, v in tga if d <= today - timedelta(days=30)), tga[0][1])),
             "Treasury's cash at the Fed. A rising TGA pulls cash out of the banking system.", "fiscal_dts", 0)

    by = {i["key"]: i for i in out["items"]}
    if "sofr_iorb" in by:
        sp = by["sofr_iorb"]["value"]
        out["reading"].append(f"SOFR is {abs(sp):.0f}bp {'above' if sp > 0 else 'below'} IORB: "
                              + ("funding is tightening, so the front end can cheapen even without a Fed move." if sp > 0 else
                                 "no funding stress, so front-end yields are trading on the Fed path, not on liquidity."))
    if "rrp" in by and by["rrp"]["value"] is not None:
        r = by["rrp"]["value"]
        out["reading"].append(f"ON RRP is ${r:.1f}bn: " + ("the money-fund buffer is used up, so bill issuance and TGA rebuilds now draw on bank reserves."
                                                         if r < 50 else "money funds still have cash to absorb bill supply."))
    if "reserves" in by:
        out["reading"].append(f"Reserves are ${by['reserves']['value']:.2f}tn ({by['reserves']['chg_1m']:+.2f}tn over a month).")
    if "tga" in by and by["tga"]["chg_1m"] is not None:
        out["reading"].append(f"The TGA is ${by['tga']['value']:.0f}bn ({by['tga']['chg_1m']:+.0f}bn over a month).")
    return out


def move_index() -> dict | None:
    m = _safe(S.yahoo_chart, "^MOVE", "1y")
    if not m or not m["hist"]:
        return None
    vals = [v for _, v in m["hist"]]
    now = m["price"]
    pct = sum(1 for v in vals if v <= now) / len(vals) * 100
    month = [v for d, v in m["hist"] if d <= date.today() - timedelta(days=30)]
    return {"level": round(now, 1), "pctile_1y": round(pct), "chg_1m": round(now - month[-1], 1) if month else None,
            "date": m["hist"][-1][0].isoformat()}


def health() -> dict:
    """As-of date and status of every data source, so stale numbers are never mistaken for current ones."""
    today = date.today()
    rows = []

    def add(name, src, fn, cadence_days, fmt=lambda x: x):
        try:
            d = fn()
            if d is None:
                rows.append({"name": name, "src": src, "asof": None, "status": "failed"})
                return
            dd = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
            age = (today - dd).days
            rows.append({"name": name, "src": src, "asof": dd.isoformat(), "status": "ok" if age <= cadence_days else "stale", "cadence": cadence_days})
        except Exception:
            rows.append({"name": name, "src": src, "asof": None, "status": "failed"})
    add("Treasury par curve", "ust_par", lambda: load_curves()[2], 4)
    add("TIPS real curve", "ust_real", lambda: max(load_curves()[1]), 4)
    add("Fed funds futures", "zq", lambda: (fed_cached().get("futures_time") or "")[:10] or None, 4)
    add("EFFR", "effr", lambda: S.effr_history(5)[0]["date"], 5)
    add("SOFR", "sofr", lambda: S.sofr_history(5)[0]["date"], 5)
    add("Business surveys", "fred:GAFDFSA066MSFRBPHI", lambda: S.fred("GAFDFSA066MSFRBPHI", today - timedelta(days=120))[-1][0], 50)
    add("CPI", "fred:CPIAUCSL", lambda: S.fred("CPIAUCSL", today - timedelta(days=150))[-1][0], 75)
    add("Neutral rate (r*)", "rstar", lambda: X.rstar()[-1][0], 200)
    add("Auctions", "td_upcoming", lambda: today if S.td_upcoming() is not None else None, 1)
    add("News (Google News)", "gnews", lambda: today if S.google_news('"Treasury yields"', when="2d") is not None else None, 1)
    return {"rows": rows, "ok": all(r["status"] == "ok" for r in rows)}


DEBT_TAGS = [("Buyback", r"buy ?backs?"), ("Refunding", r"refunding"),
             ("Borrowing estimate", r"borrowing (estimate|need)|marketable borrowing|financing estimates?"),
             ("Auction sizes", r"auctions?\b|coupon sizes?|issuance|bill supply|treasury bills?\b"),
             ("Debt management", r"debt management|\btbac\b|borrowing advisory|debt limit|debt ceiling|\bdebt\b.*\btreasur")]


def treasury_news() -> dict:
    qs = [('site:home.treasury.gov (buyback OR refunding OR borrowing OR auction OR "debt management" OR financing)', "90d"),
          ('("Treasury buyback" OR buybacks OR "quarterly refunding" OR "auction sizes" OR "coupon auction" '
           'OR "Treasury borrowing" OR "bill issuance") Treasury', "30d")]
    with ThreadPoolExecutor(2) as ex:
        lists = list(ex.map(lambda q: _safe(S.google_news, q[0], when=q[1]) or [], qs))
    seen, items = set(), []
    for lst in lists:
        for it in lst:
            k = re.sub(r"\W+", "", it["title"].lower())[:90]
            if k in seen:
                continue
            seen.add(k)
            tags = [n for n, rx in DEBT_TAGS if re.search(rx, it["title"], re.I)]
            if tags:
                items.append(dict(it, tags=tags))
    items.sort(key=lambda i: i["published"] or "", reverse=True)

    ops = []
    for o in _safe(S.buyback_operations, 30) or []:
        g = lambda k: None if o.get(k) in (None, "null", "") else o.get(k)
        ops.append({"date": g("operation_date"), "settle": g("settlement_date"), "type": g("operation_type"),
                    "security_type": g("security_type"), "bucket": g("maturity_bucket"),
                    "max_bn": (_f(g("max_par_amt_redeemed")) or 0) / 1e9 or None,
                    "offered_bn": (_f(g("total_par_amt_offered")) or 0) / 1e9 or None,
                    "accepted_bn": (_f(g("total_par_amt_accepted")) or 0) / 1e9 or None,
                    "eligible": g("nbr_issues_eligible"), "accepted_issues": g("nbr_issues_accepted")})
    return {"news": items[:30], "buybacks": ops}

