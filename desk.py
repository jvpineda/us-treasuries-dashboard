"""The executive summary, written the way a macro PM writes a morning note.

Order of a desk note: how big was it (in sigma and in history), what is priced, what drove it, what the rest of the
tape says. Short windows that are noise are called noise and pointed back at the regime that matters.
"""
from __future__ import annotations

from datetime import date

from narrative import lc

LEAD = {
    "Bear flattener": "front end leading the selloff", "Bear steepener": "long end leading the selloff",
    "Bull steepener": "front end leading the rally", "Bull flattener": "long end leading the rally",
    "Twist flattener": "front end higher, long end lower", "Twist steepener": "front end lower, long end higher",
    "Parallel bear shift": "a level selloff across the curve", "Parallel bull shift": "a level rally across the curve",
    "Little changed": "flat on the window",
}
# The PM's one-line read of each shape.
READ = {
    "Bear flattener": "the market is pricing a Fed that has to lean against a hot economy",
    "Twist flattener": "hawkish Fed, and the market thinks it ends up slowing growth",
    "Parallel bear shift": "a repricing of the whole rates complex rather than just the next few meetings",
    "Bear steepener": "the market wants more compensation to own duration: growth, inflation risk or supply",
    "Bull steepener": "the market is pricing cuts",
    "Twist steepener": "easier Fed now, more inflation or supply risk further out",
    "Bull flattener": "duration bid: the market is buying long bonds on growth fears",
    "Parallel bull shift": "a level rally, with no single segment leading",
    "Little changed": "nothing priced in or out",
}


def _m(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.year}"


def _bp(v):
    return f"{'+' if v > 0 else '−' if v < 0 else '±'}{abs(v):.0f}bp"


def _z(z):
    return f"{abs(z):.1f}σ"


def _hist_phrase(row, horizon_name, past=None, asof=None):
    """'largest 1-year rise in the 2Y since Sep 2023', only when that is genuinely a long time ago."""
    ls = row.get("largest_since")
    if not ls or (past and asof and (asof - past).days > 3700):
        return ""
    if ls.get("date") and past and asof:
        gap = (past - date.fromisoformat(ls["date"])).days
        if gap < max(180, 2 * (asof - past).days):
            return ""
    word = "rise" if row["chg_bp"] > 0 else "fall"
    if ls.get("date") is None:
        return f"largest {horizon_name} {word} in the {row['label']} on record (since {ls['since'][:4]})"
    return f"largest {horizon_name} {word} in the {row['label']} since {_m(ls['date'])}"


def _level_phrase(lv, tenor, now, up):
    x = (lv or {}).get(tenor)
    if not x:
        return ""
    if x.get("date") is None:
        return f"{'highest' if up else 'lowest'} on record"
    d = date.fromisoformat(x["date"])
    return f"{'highest' if up else 'lowest'} since {d:%b} {d.year}" if (date.today() - d).days > 180 else ""


def horizon_name(past: date, asof: date) -> str:
    days = (asof - past).days
    if days <= 4:
        return "1-day"
    if days <= 9:
        return "1-week"
    if days <= 45:
        return "1-month"
    if days <= 120:
        return "3-month"
    if days <= 400:
        return "1-year"
    return f"{round(days / 365.25)}-year"


def build(a, mode, tr, cross, rr, regime_1y, fed, k, moves, sv, themes, flip_detail, eps):
    T = {t["tenor"]: t for t in a["tenors"]}
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    hn = horizon_name(past, asof)
    regime = a["regime"]
    rows = {r["key"]: r for r in tr["rows"]}
    r2, r10 = rows["2Y"], rows["10Y"]
    d10 = r10["chg_bp"] or 0
    up = d10 >= 0
    grade = tr["grade"]["label"] if mode == "near" else "Long view"
    lvl10 = _level_phrase(tr["levels"], "10Y", T["10Y"]["today"], up)
    real, be = rows.get("real10"), rows.get("be10")

    def driver_clause():
        if not real or not be or abs(d10) < 5:
            return ""
        rb, bb = real["chg_bp"], be["chg_bp"]
        if abs(rb) >= 2 * abs(bb):
            return (f" Real yields did the {'lifting' if rb > 0 else 'work'} ({_bp(rb)}, breakevens {_bp(bb)}): "
                    + ("a Fed and growth repricing, not an inflation scare." if rb > 0 else "a growth and Fed story, not disinflation."))
        if abs(bb) >= 2 * abs(rb):
            return f" Breakevens drove it ({_bp(bb)}, real yields {_bp(rb)}): an inflation-risk trade."
        return f" Split between real yields ({_bp(rb)}) and breakevens ({_bp(bb)})."

    # ---- Headline ----
    if mode != "near":
        h2, h10 = _hist_phrase(r2, hn, past, asof), _hist_phrase(r10, hn, past, asof)
        headline = (f"{hn[0].upper() + hn[1:]} view: 10Y {T['10Y']['past']:.2f}% → {T['10Y']['today']:.2f}% ({_bp(d10)})"
                    + (f", the {h10}" if h10 else "") + f"; 2Y {_bp(r2['chg_bp'])}."
                    + (f" 10Y {lvl10}." if lvl10 else "")
                    + (f" The regime that matters now is the 1-year {regime_1y.lower()}: {READ.get(regime_1y, '')}." if regime_1y else ""))
    elif grade == "Noise":
        loud = max((r for r in tr["rows"] if r["z"] is not None), key=lambda r: abs(r["z"]), default=None)
        headline = (f"Noise. 10Y {_bp(d10)}, 2Y {_bp(r2['chg_bp'])}: {_z(r10['z'])} and {_z(r2['z'])} of a normal {hn} move."
                    + (f" The only part worth a look is {loud['label']} {_bp(loud['chg_bp'])} ({_z(loud['z'])})."
                       if loud and abs(loud["z"]) >= 1.5 else "")
                    + (f" Nothing here changes the 1-year {regime_1y.lower()}: {READ.get(regime_1y, '')}." if regime_1y else ""))
    else:
        lead = max((r2, r10), key=lambda r: abs(r["z"] or 0))
        hp = _hist_phrase(lead, hn, past, asof) or _hist_phrase(r10 if lead is r2 else r2, hn, past, asof)
        headline = (f"{regime}, {LEAD.get(regime, '')}: 2Y {_bp(r2['chg_bp'])} ({_z(r2['z'])}), 10Y {_bp(d10)} "
                    f"to {T['10Y']['today']:.2f}%" + (f", {lvl10}" if lvl10 else "") + "."
                    + (f" That is the {hp}." if hp else "")
                    + driver_clause())

    # ---- Bullets: window-specific ----
    bullets = []
    pr = _pricing(a, fed, flip_detail, mode)
    if pr:
        bullets.append({"label": "Priced", "text": pr})
    cat = _catalysts(k, moves, sv, themes, mode, eps, hn)
    if cat:
        bullets.append({"label": "Drivers", "text": cat})
    xa = _cross(cross, rr if mode == "near" else None, grade, mode)
    if xa:
        bullets.append({"label": "Cross-asset", "text": xa})
    su = _surveys(sv, mode)
    if su:
        bullets.append({"label": "Surveys", "text": su})
    return {"headline": headline, "grade": tr["grade"] if mode == "near" else {"label": "Long view", "cls": ""},
            "bullets": bullets, "rates": tr["rows"], "cross": cross, "regime_read": rr, "levels": tr["levels"],
            "horizon_name": hn}


def _pricing(a, fed, flip_detail, mode):
    if not fed or not fed.get("meetings"):
        return ""
    m = fed["meetings"]
    nxt, last = m[0], m[-1]
    odds = {"hold": nxt["p_hold"], "hike": nxt["p_hike"], "cut": nxt["p_cut"]}
    top = max(odds, key=odds.get)
    other = [f"{v * 100:.0f}% {k_}" for k_, v in odds.items() if k_ != top and v >= 0.01]
    d = date.fromisoformat(last["date"])
    txt = (f"{date.fromisoformat(nxt['date']):%b} {date.fromisoformat(nxt['date']).day} FOMC {odds[top] * 100:.0f}% {top}"
           + (f" / {', '.join(other)}" if other else "")
           + f"; {_bp(last['cum_bp'])} (≈{abs(last['cum_bp']) / 25:.1f} {'hikes' if last['cum_bp'] > 0 else 'cuts'}) priced through {d:%b} '{d:%y}.")
    hist = fed.get("history") or {}
    days = (date.fromisoformat(a["asof"]) - date.fromisoformat(a["past"])).days
    key = None if days <= 4 else "1W" if days <= 9 else "1M" if days <= 45 else None
    if key and hist.get(key) and last.get(f"shift_{key}_bp") is not None:
        sh = last[f"shift_{key}_bp"]
        txt += (f" {abs(sh):.0f}bp {'more hawkish' if sh > 0 else 'more dovish'} than a {'week' if key == '1W' else 'month'} ago."
                if abs(sh) >= 2 else f" Little changed from a {'week' if key == '1W' else 'month'} ago.")
    elif flip_detail and days > 45:
        txt += f" Over the window {flip_detail}."
    return txt


def _catalysts(k, moves, sv, themes, mode, eps, hn):
    """What actually happened inside this window: releases, Fed decisions, the story the news ran."""
    if mode != "near":
        big = sorted(eps, key=lambda e: -max(abs(e.get("d10") or 0), e.get("swing") or 0))[:3]
        return "; ".join(f"{e['title']} ({_m(e['from'])}–{_m(e['to'])}{', 10Y ' + _bp(e['d10']) if e.get('d10') is not None else ''})"
                         for e in sorted(big, key=lambda e: e["from"])) + "."
    out = []

    def new(key):
        r = k.get(key)
        return r and r.get("then") and r["then"]["period"] != r["now"]["period"]
    if new("cpi"):
        c, cc = k["cpi"], k.get("core_cpi")
        out.append(f"CPI {c['then']['value']:.1f}% → {c['now']['value']:.1f}% y/y ({c['now']['period']})"
                   + (f", core {cc['now']['value']:.1f}%" if cc else "")
                   + (": energy, not broad-based" if cc and c["now"]["value"] - cc["now"]["value"] >= 0.5 and c["now"]["value"] > c["then"]["value"] else ""))
    if new("unrate") and abs(k["unrate"]["now"]["value"] - k["unrate"]["then"]["value"]) >= 0.2:
        u, p = k["unrate"], k.get("payrolls")
        out.append(f"unemployment {u['then']['value']:.1f}% → {u['now']['value']:.1f}%"
                   + (f", payrolls {p['now']['value']:,.0f}k/mo (3m avg)" if p else ""))
    oil = k.get("oil")
    if oil and oil.get("then") and abs(oil["now"]["value"] / oil["then"]["value"] - 1) >= 0.1:
        out.append(f"WTI ${oil['then']['value']:.0f} → ${oil['now']['value']:.0f}")
    it = {s["key"]: s for s in sv}.get("it_invest")
    if it and it.get("then_period") != it["now_period"] and it["now"] >= 6:
        out.append(f"AI capex: tech investment +{it['now']:.0f}% y/y ({it['now_period']})")
    if moves:
        out.append("Fed " + ", ".join(f"{'+' if bp > 0 else '−'}{abs(bp)}bp ({date.fromisoformat(d.isoformat()):%b %-d})" for d, bp in moves))
    j = k.get("jgb10")
    if j and j.get("then") and j["now"]["value"] - j["then"]["value"] >= 0.25:
        out.append(f"JGB 10Y {j['then']['value']:.2f}% → {j['now']['value']:.2f}%")
    top = [t for t in (themes or []) if t.get("volume")][:2]
    if top and len(out) < 3:
        out.append("news flow: " + ", ".join(f"{lc(t['name'])} ({t['volume']} stories)" for t in top))
    if not out:
        return f"No scheduled data or Fed action in the {hn} window."
    s = "; ".join(out[:5])
    return s[0].upper() + s[1:] + "."


def _fmt_x(c):
    if c["kind"] == "pct":
        v = f"{'+' if c['chg'] > 0 else '−'}{abs(c['chg']):.1f}%"
    else:
        v = f"{c['then']:.0f} → {c['now']:.0f}"
    return f"{c['label']} {v}" + (f" ({abs(c['z']):.1f}σ)" if c.get("z") is not None and abs(c["z"]) >= 1 else "")


def _cross(cross, rr, grade, mode):
    if not cross:
        return ""
    by = {c["sym"]: c for c in cross}
    order = ["^GSPC", "DX-Y.NYB", "CL=F", "GC=F", "^VIX", "^MOVE"]
    if grade == "Noise":
        loud = [c for c in cross if c.get("z") is not None and abs(c["z"]) >= 1]
        if not loud:
            return "Quiet across assets: nothing moved more than one standard deviation."
        return "The action was elsewhere: " + ", ".join(_fmt_x(c) for c in loud) + "."
    parts = ", ".join(_fmt_x(by[s]) for s in order if s in by and (by[s]["kind"] != "pct" or abs(by[s]["chg"]) >= 0.5))
    if rr:
        return f"{rr['name']}: {parts}. {rr['read'][0].upper() + rr['read'][1:]}. {rr['fx']}"
    return parts + "."


def _surveys(sv, mode):
    """Only the surveys that printed inside the window, with their change over it."""
    fresh = [s for s in sv if s.get("then") is not None and s.get("then_period") != s["now_period"]
             and s["key"] in ("outlook", "capex_plans", "capex_orders", "sentiment")]
    if not fresh:
        return ""
    def f(s, v):
        return f"{v:.1f}%" if s["unit"] != "index" else f"{v:.0f}"
    short = {"outlook": "Philly outlook", "capex_plans": "Philly capex plans", "capex_orders": "core capex orders",
             "it_invest": "tech investment", "sentiment": "UMich sentiment", "infl_exp": "UMich 1y inflation exp."}
    bits = [f"{short.get(s['key'], s['label'])} {f(s, s['then'])} → {f(s, s['now'])} (avg {f(s, s['avg'])})" for s in fresh]
    biz = [s for s in fresh if s["side"] in ("business", "ai")]
    cons = [s for s in fresh if s["key"] == "sentiment"]
    tag = ""
    if biz and cons:
        b_up = sum(s["now"] > s["then"] for s in biz) > len(biz) / 2
        c_up = cons[0]["now"] > cons[0]["then"]
        tag = (" Capex boom, consumer squeeze." if b_up and not c_up else " Both sides improving." if b_up and c_up
               else " Businesses cooling, consumers firmer." if c_up else " Both sides softening.")
    if biz and not cons:
        b_up = sum(s["now"] > s["then"] for s in biz) > len(biz) / 2
        high = all(s["now"] > s["avg"] for s in biz)
        tag = (" Business surveys improving." if b_up else
               " Businesses cooling off from very strong levels, still above average." if high else " Business surveys softening.")
    return "; ".join(bits) + "." + tag
