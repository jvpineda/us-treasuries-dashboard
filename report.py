"""The executive summary as a report: complete sentences a rates trader can paste to their head of trading.

Structure, every window:
  Bottom line   one sentence: what the curve did and why.
  The move      size and shape, in context (history and normal volatility).
  Monetary      the Fed, inflation and what the market now prices.
  The economy   the main themes: AI investment, energy, jobs, consumers.
  Fiscal/global deficits, auctions, bills, rates abroad.
  The read      what the rest of the market says, and what comes next.
Short windows that are noise get a short report that says so and restates the bigger picture.
"""
from __future__ import annotations

from datetime import date

from narrative import lc

NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
WHEN = {"1-day": "on the day", "1-week": "over the past week", "1-month": "over the past month",
        "3-month": "over the past three months", "1-year": "over the past year"}
SINCE = {"1-day": "the previous close", "1-week": "a week ago", "1-month": "a month ago", "3-month": "three months ago",
         "1-year": "a year ago"}


def _month(iso_or_date):
    d = iso_or_date if isinstance(iso_or_date, date) else date.fromisoformat(iso_or_date)
    return f"{d:%B} {d.year}"


def _day(d):
    d = d if isinstance(d, date) else date.fromisoformat(d)
    return f"{d:%B} {d.day}"


def _n(x):
    return NUM.get(x, str(x))


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def _join(xs):
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


THEME_NOUN = {"ai_capex": "the AI investment boom", "energy": "oil and Iran tensions", "global": "the global bond selloff",
              "fed_politics": "Fed independence", "deficits": "deficits and Treasury supply", "tariffs": "tariffs",
              "jobs": "the job market", "housing": "housing", "ai_disruption": "AI disruption of software and jobs"}


def _period(p):
    """'Sep 2026' -> 'September'."""
    try:
        from datetime import datetime
        return datetime.strptime(p, "%b %Y").strftime("%B")
    except ValueError:
        return p


def _times(x):
    return "roughly double" if 1.8 <= x < 2.5 else "roughly triple" if 2.5 <= x < 3.5 else f"about {x:.0f} times"


def _sec(name):
    return name.split(" (")[0].replace("-Year Note", "-year note").replace("-Year Bond", "-year bond").replace("-Year TIPS", "-year TIPS")


def build(a, mode, tr, cross, rr, regime_1y, fed, k, moves, sv, themes, eps, auc, dc, hn):
    T = {t["tenor"]: t for t in a["tenors"]}
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    rows = {r["key"]: r for r in tr["rows"]}
    d2, d10, d30 = (T[x]["chg_bp"] or 0 for x in ("2Y", "10Y", "30Y"))
    s2 = a["spreads"]["2s10s"]
    regime = a["regime"]
    when = WHEN.get(hn, f"since {_day(past)}, {past.year}")
    svk = {s["key"]: s for s in sv}
    noise = mode == "near" and tr["grade"]["label"] == "Noise"
    level = (d2 + d10 + d30) / 3
    sold = level > 0

    if mode != "near":
        return _long(a, T, rows, d2, d10, s2, regime_1y, fed, k, sv, svk, eps, dc, auc, past, asof, tr, hn)

    # ---------------- The move ----------------
    lv10 = (tr["levels"] or {}).get("10Y") or {}
    lvl_txt = ""
    if lv10.get("date") and (asof - date.fromisoformat(lv10["date"])).days > 365:
        lvl_txt = f", its {'highest' if d10 > 0 else 'lowest'} level since {_month(lv10['date'])}"
    front_led = abs(d2) > abs(d30)
    shape = ("flattened" if (s2["chg"] or 0) < 0 else "steepened") if abs(s2["chg"] or 0) >= 2 else "held its shape"
    if noise:
        loud = max((r for r in tr["rows"] if r["z"] is not None), key=lambda r: abs(r["z"]), default=None)
        move = (f"Treasuries were little changed {when}: the 10-year {'rose' if d10 > 0 else 'fell' if d10 < 0 else 'was flat'}"
                f"{f' {abs(d10):.0f}bp' if d10 else ''} to {T['10Y']['today']:.2f}% and the 2-year "
                f"{'rose' if d2 > 0 else 'fell' if d2 < 0 else 'was flat'}{f' {abs(d2):.0f}bp' if d2 else ''} to {T['2Y']['today']:.2f}%, "
                f"well inside a normal {hn.replace('1-', '')}'s range.")
        if loud and abs(loud["z"]) >= 1.5 and loud["key"] not in ("2Y", "10Y"):
            move += (f" The one move of note was in {loud['label']}, which "
                     f"{'rose' if loud['chg_bp'] > 0 else 'fell'} {abs(loud['chg_bp']):.0f}bp, a larger-than-usual move for a {hn.replace('1-', '')}.")
    else:
        lead = "front end" if front_led else "long end"
        move = (f"The 2-year "
                f"{'rose' if d2 > 0 else 'fell'} {abs(d2):.0f}bp to {T['2Y']['today']:.2f}% and the 10-year "
                f"{'rose' if d10 > 0 else 'fell'} {abs(d10):.0f}bp to {T['10Y']['today']:.2f}%{lvl_txt}, while the 2s10s curve "
                f"{shape}{f' {abs(s2['chg']):.0f}bp' if shape != 'held its shape' else ''} to {s2['today']:+.0f}bp.")
        r2, r10 = rows["2Y"], rows["10Y"]
        big = max((r2, r10), key=lambda r: abs(r["z"] or 0))
        ls = big.get("largest_since") or {}
        size = ""
        if big["z"] is not None:
            z = abs(big["z"])
            size = (f"{'an outsized' if z >= 2 else 'a sizeable' if z >= 1 else 'a modest'} move against normal volatility "
                    f"(about {z:.1f} standard deviations)")
        word = "rise" if big["chg_bp"] > 0 else "fall"
        span = hn.replace("1-", "one-").replace("3-", "three-")
        if ls.get("date") and (past - date.fromisoformat(ls["date"])).days > max(180, 2 * (asof - past).days):
            move += (f" That is the largest {span} {word} in the {big['label'].replace('Y', '-year')} since {_month(ls['date'])}"
                     + (f", {size}." if size else "."))
        elif size:
            move += f" It is {size}."

    # ---------------- Monetary ----------------
    mon = []
    cpi, core, oil = k.get("cpi"), k.get("core_cpi"), k.get("oil")
    cpi_new = cpi and cpi.get("then") and cpi["then"]["period"] != cpi["now"]["period"]
    oil_big = oil and oil.get("then") and abs(oil["now"]["value"] / oil["then"]["value"] - 1) >= 0.1
    cuts = [(d, bp) for d, bp in moves if bp < 0]
    hikes = [(d, bp) for d, bp in moves if bp > 0]
    fe = _front(a, k)
    if not noise and fe and fe["flip"]:
        mon.append(f"{_cap(SINCE.get(hn, 'at the start of the window'))} the 2-year sat {abs(fe['g0']):.0f}bp "
                   f"{'below' if fe['g0'] < 0 else 'above'} fed funds, a market pricing {'cuts' if fe['g0'] < 0 else 'hikes'}; "
                   f"it now sits {abs(fe['g1']):.0f}bp {'below' if fe['g1'] < 0 else 'above'}, pricing {'cuts' if fe['g1'] < 0 else 'hikes'}.")
    if cuts and hikes:
        mon.append(f"The Fed cut {-sum(bp for _, bp in cuts)}bp ({_join([_month(d) for d, _ in cuts])}) before reversing course "
                   f"with a {sum(bp for _, bp in hikes)}bp hike in {_join([_month(d) for d, _ in hikes])}"
                   + (f", as oil rose from ${oil['then']['value']:.0f} to ${oil['now']['value']:.0f} a barrel and headline CPI climbed "
                      f"from {cpi['then']['value']:.1f}% to {cpi['now']['value']:.1f}%" if oil_big and cpi_new and cpi["now"]["value"] > cpi["then"]["value"] else "")
                   + ".")
    elif hikes:
        mon.append(f"The Fed raised rates {sum(bp for _, bp in hikes)}bp in {_join([_month(d) for d, _ in hikes])}.")
    elif cuts:
        mon.append(f"The Fed cut rates {-sum(bp for _, bp in cuts)}bp ({_join([_month(d) for d, _ in cuts])}).")
    if cpi_new and not (cuts and hikes and oil_big):
        narrow = core and cpi["now"]["value"] - core["now"]["value"] >= 0.5
        mon.append(f"{_period(cpi['now']['period'])} CPI {'rose' if cpi['now']['value'] > cpi['then']['value'] else 'eased'} "
                   f"to {cpi['now']['value']:.1f}% from {cpi['then']['value']:.1f}%"
                   + (f", but core was {core['now']['value']:.1f}%, so the pickup is energy rather than broad-based price pressure."
                      if narrow else f", with core at {core['now']['value']:.1f}%." if core else "."))
    elif core and cuts and hikes and oil_big:
        mon.append(f"Core CPI is only {core['now']['value']:.1f}%, so the inflation problem is energy, not broad-based.")
    if fed and fed.get("meetings"):
        m, last = fed["meetings"][0], fed["meetings"][-1]
        top = max(("hold", m["p_hold"]), ("hike", m["p_hike"]), ("cut", m["p_cut"]), key=lambda x: x[1])
        alt = [f"a {p * 100:.0f}% chance of a {w}" for w, p in (("hike", m["p_hike"]), ("cut", m["p_cut"])) if p >= 0.05 and w != top[0]]
        nh = abs(last["cum_bp"]) / 25
        txt = (f"Futures now price about {nh:.1f} {'hikes' if last['cum_bp'] > 0 else 'cuts'} by {_month(last['date'])}"
               f" and {'a hold' if top[0] == 'hold' else 'a ' + top[0]} at the {_day(m['date'])} meeting"
               + (f", with {_join(alt)}" if alt else "") + ".")
        key = "1W" if hn == "1-week" else "1M" if hn == "1-month" else None
        if key and last.get(f"shift_{key}_bp") is not None and abs(last[f"shift_{key}_bp"]) >= 3:
            sh = last[f"shift_{key}_bp"]
            txt = txt[:-1] + f", {abs(sh):.0f}bp {'more hawkish' if sh > 0 else 'more dovish'} than {SINCE[hn]}."
        mon.append(txt)
    real, be = rows.get("real10"), rows.get("be10")
    if not noise and real and be and abs(d10) >= 8:
        rb, bb = real["chg_bp"], be["chg_bp"]
        if abs(rb) >= 2 * abs(bb):
            mon.append(f"Nearly all of the 10-year's move came through real yields ({rb:+.0f}bp) rather than inflation breakevens "
                       f"({bb:+.0f}bp): the market is repricing growth and the policy path, "
                       f"{'not losing faith in inflation control' if rb > 0 else 'not pricing a collapse in inflation'}.")
        elif abs(bb) >= 2 * abs(rb):
            mon.append(f"Most of the 10-year's move came through inflation breakevens ({bb:+.0f}bp) rather than real yields "
                       f"({rb:+.0f}bp): this is an inflation-risk trade.")

    # ---------------- The economy ----------------
    eco = []
    it, cap, plans, sent, outlook = (svk.get(x) for x in ("it_invest", "capex_orders", "capex_plans", "sentiment", "outlook"))
    long_enough = (asof - past).days >= 80
    if long_enough or not noise:
        if it and it["now"] >= 6:
            bits = [f"spending on computers, software and data-center equipment is up {it['now']:.0f}% from a year earlier"]
            if cap and cap["now"] >= 5:
                bits.append(f"core capital goods orders are up {cap['now']:.0f}%")
            sent_plans = ""
            if plans and plans["now"] > 1.5 * plans["avg"]:
                moved = plans.get("then") is not None and plans["then_period"] != plans["now_period"]
                sent_plans = (f", and the Philadelphia Fed's gauge of capex plans "
                              + (f"has {'risen' if plans['now'] > plans['then'] else 'eased'} from {plans['then']:.0f} to {plans['now']:.0f}"
                                 if moved else f"stands at {plans['now']:.0f}")
                              + f", {_times(plans['now'] / plans['avg'])} its long-run average")
            eco.append(f"The economy behind it is running hot on AI investment: {_join(bits)}{sent_plans}.")
        u = k.get("unrate")
        if u and long_enough:
            p = k.get("payrolls")
            eco.append(f"The labor market is holding up, with unemployment at {u['now']['value']:.1f}%"
                       + (f" and payrolls growing about {p['now']['value']:.0f}k a month" if p else "") + "."
                       if u["now"]["value"] <= 4.5 else f"The labor market is softening, with unemployment at {u['now']['value']:.1f}%.")
        if sent and not sent["strong"] and long_enough:
            eco.append(f"The weak spot is the consumer: Michigan sentiment is {sent['now']:.0f}, far below its {sent['avg']:.0f} average"
                       + (", as fuel costs and borrowing costs climb." if oil_big and oil["now"]["value"] > oil["then"]["value"] else "."))
        top = [t for t in (themes or []) if t.get("volume")][:2]
        if not long_enough and top:
            eco.append(f"News flow tying the move to rates centred on {THEME_NOUN.get(top[0]['key'], lc(top[0]['name']))}"
                       + (f" and {THEME_NOUN.get(top[1]['key'], lc(top[1]['name']))}" if len(top) > 1 else "") + ".")
        if not long_enough and outlook and outlook.get("then") is not None and outlook["then_period"] != outlook["now_period"]:
            eco.append(f"The Philadelphia Fed business outlook printed {outlook['now']:.0f}, "
                       f"{'down' if outlook['now'] < outlook['then'] else 'up'} from {outlook['then']:.0f} but still "
                       f"{'well above' if outlook['now'] > outlook['avg'] else 'below'} its {outlook['avg']:.0f} average.")

    # ---------------- Fiscal and global ----------------
    fis = []
    dm = ((auc or {}).get("summary") or {}).get("metrics") or {}
    if long_enough:
        dfc = k.get("deficit")
        if dfc:
            fis.append(f"The federal deficit is running at ${dfc['now']['value']:.1f} trillion over the past 12 months")
        de = dm.get("demand")
        if de and de["reads"]:
            soft = [_sec(r["security"]) for r in de["reads"] if r["quality"] == "Soft"]
            strong = [_sec(r["security"]) for r in de["reads"] if r["quality"] == "Strong"]
            if len(soft) >= 3:
                fis.append(f"coupon supply is being absorbed only grudgingly, with {_n(len(soft))} of the last ten auctions tailing "
                           f"against the market, including the {_join(soft[:3])}")
            elif strong and len(strong) >= len(soft):
                fis.append(f"coupon auctions have gone well, with {_n(len(strong))} of the last ten stopping through")
            else:
                fis.append("coupon auctions have been absorbed in line with the market")
        j = k.get("jgb10")
        if j and j.get("then") and j["now"]["value"] - j["then"]["value"] >= 0.3:
            fis.append(f"abroad, Japan's 10-year yield climbed from {j['then']['value']:.2f}% to {j['now']['value']:.2f}%, pulling "
                       f"global capital back home and adding pressure on the long end")
    else:
        recent = [r for r in (auc or {}).get("recent_coupons", []) if past.isoformat() < r["auction_date"] <= asof.isoformat()]
        for r in recent[:2]:
            q = r.get("quality") or "In line"
            t = (r.get("avg") or {}).get("tail_bp")
            fis.append(f"the {_sec(r['security'])} auction on {_day(r['auction_date'])} "
                       + ({"Soft": f"tailed{f' by about {t:.1f}bp' if t else ''} against the market",
                           "Strong": f"stopped through the market{f' by about {abs(t):.1f}bp' if t else ''}"}.get(q, "came in line with the market")))
    fis_txt = (_cap("; ".join(fis)) + ".") if fis else ""

    # ---------------- The read and what is next ----------------
    read = []
    by = {c["sym"]: c for c in cross}
    spx, dxy = by.get("^GSPC"), by.get("DX-Y.NYB")
    if noise:
        loud = [c for c in cross if c.get("z") is not None and abs(c["z"]) >= 1]
        if loud:
            read.append("The action was in other markets: " + _join([
                f"the {c['label']} {'rose' if c['chg'] > 0 else 'fell'} {abs(c['chg']):.1f}{'%' if c['kind'] == 'pct' else ' points'}"
                for c in loud]) + ".")
        if regime_1y:
            read.append(f"Nothing here changes the bigger picture: over the past year the curve has bear-flattened as the market "
                        f"priced a Fed leaning against a hot economy." if regime_1y == "Bear flattener" else
                        f"The bigger picture is unchanged: over the past year the curve has moved in a {regime_1y.lower()}.")
    elif spx and rr:
        tone = {"Growth-led selloff": "the profile of a growth-led selloff rather than a rates shock",
                "Rates shock": "a rates shock that is tightening financial conditions",
                "Goldilocks rally": "a goldilocks rally on easier policy",
                "Risk-off": "a risk-off move with bonds hedging equities"}.get(rr["name"], "")
        read.append(f"Risk assets {'took it in stride' if spx['chg'] > 0 else 'did not'}: the S&P 500 "
                    f"{'rose' if spx['chg'] > 0 else 'fell'} {abs(spx['chg']):.0f}%"
                    + (f" and the dollar {'rose' if dxy['chg'] > 0 else 'fell'} {abs(dxy['chg']):.1f}%" if dxy else "")
                    + (f", {tone}." if tone else "."))
        if dxy and d10 > 0 and dxy["chg"] < -1:
            read.append("A weaker dollar alongside higher yields is a warning sign on fiscal credibility worth watching.")
    ev = []
    if fed and fed.get("meetings"):
        ev.append((fed["meetings"][0]["date"], f"the FOMC on {_day(fed['meetings'][0]['date'])}"))
    for u in ((auc or {}).get("coupons") or [])[:2]:
        ev.append((u["auction_date"], f"the {_sec(u['security'])} auction on {_day(u['auction_date'])}"))
    watch = [t for _, t in sorted(ev)]
    if watch:
        mood_risk = ("a soft core print or a pullback in AI capex would be the pain trade, with the front end rallying first"
                     if sold and front_led else
                     "strong long-end demand at auction or calmer global yields would pull the long end back first"
                     if sold else "a hot inflation print would challenge the rally")
        read.append(f"Next up are {_join(watch)}" + ("" if noise else f"; {mood_risk}") + ".")

    # ---------------- Bottom line ----------------
    drivers = []
    if hikes and cuts:
        drivers.append("the Fed's turn from cuts to hikes")
    elif hikes:
        drivers.append(f"the Fed's {_period(hikes[-1][0].strftime('%b %Y'))} hike")
    elif cuts:
        drivers.append("Fed cuts")
    elif fe and fe["flip"]:
        drivers.append("a swing in Fed pricing")
    if cpi_new and not long_enough and cpi["now"]["value"] > cpi["then"]["value"]:
        drivers.append("an energy-driven rise in headline inflation" if core and cpi["now"]["value"] - core["now"]["value"] >= 0.5 else "firmer inflation")
    top_t = [t for t in (themes or []) if t.get("volume")][:1]
    if top_t and not long_enough and top_t[0]["key"] in THEME_NOUN:
        drivers.append(THEME_NOUN[top_t[0]["key"]])
    if it and it["now"] >= 6 and long_enough:
        drivers.append("an AI-driven investment boom")
    if oil_big and long_enough:
        drivers.append(f"oil {'rising' if oil['now']['value'] > oil['then']['value'] else 'falling'} to ${oil['now']['value']:.0f}")
    if noise:
        bottom = (f"A quiet {hn.replace('1-', '')} in Treasuries; the move is within normal ranges and does not change the hawkish "
                  f"repricing of the past year." if regime_1y in ("Bear flattener", "Twist flattener", "Parallel bear shift")
                  else f"A quiet {hn.replace('1-', '')} in Treasuries; the move is within normal ranges.")
    else:
        bottom = (f"Treasuries {'sold off' if sold else 'rallied'} {when}, led by the {'front end' if front_led else 'long end'}"
                  + (f", on {_join(drivers)}." if drivers else "."))

    paras = [move, " ".join(mon), " ".join(eco), fis_txt, " ".join(read)]
    labels = ["The move", "Monetary", "The economy", "Fiscal and global", "The read"]
    out = [{"label": l, "text": p} for l, p in zip(labels, paras) if p]
    return {"bottom_line": bottom, "paras": out}


def _front(a, k):
    t2 = {t["tenor"]: t for t in a["tenors"]}.get("2Y")
    ff = k.get("fedfunds")
    if not t2 or not ff or not ff.get("then"):
        return None
    g0 = (t2["past"] - (ff["then"]["value"] - 0.125)) * 100
    g1 = (t2["today"] - (ff["now"]["value"] - 0.125)) * 100
    return {"g0": g0, "g1": g1, "flip": (g0 < -15 and g1 > 15) or (g0 > 15 and g1 < -15)}


def _long(a, T, rows, d2, d10, s2, regime_1y, fed, k, sv, svk, eps, dc, auc, past, asof, tr, hn):
    yrs = round((asof - past).days / 365.25)
    r10 = rows["10Y"]
    ls = r10.get("largest_since") or {}
    ctx = (f", the largest rise over a {yrs}-year span since {ls['date'][:4]}" if ls.get("date") and yrs <= 10 and d10 > 0 else
           f", the largest fall over a {yrs}-year span since {ls['date'][:4]}" if ls.get("date") and yrs <= 10 else "")
    move = (f"Over the past {yrs} years the 10-year has gone from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}%"
            f"{ctx}, and the 2-year from {T['2Y']['past']:.2f}% to {T['2Y']['today']:.2f}%.")
    big = sorted(eps, key=lambda e: -max(abs(e.get("d10") or 0), e.get("swing") or 0))[:4]
    big = sorted(big, key=lambda e: e["from"])
    chap = []
    for e in big:
        if e.get("swing") and e["swing"] >= 2 * max(abs(e.get("d10") or 0), 25):
            yt = f"the 10-year swinging between {e['lo']:.2f}% and {e['hi']:.2f}%"
        elif e.get("d10") is not None:
            yt = f"the 10-year {'rising' if e['d10'] > 0 else 'falling'} from {e['y10_from']:.2f}% to {e['y10_to']:.2f}%"
        else:
            yt = ""
        y0, y1 = e["from"][:4], e["to"][:4]
        yrs_txt = y0 if y0 == y1 else f"{y0}–{y1[2:]}"
        how = "" if e.get("data_only") else f"{lc(e['channel'])}, "
        chap.append(f"{lc(e['title'])} ({yrs_txt}): {how}with {yt}")
    path = ("The path ran through " + "; ".join(chap) + ".") if chap else ""
    cur = eps[-1] if eps else None
    now = []
    if cur:
        now.append(f"The current chapter is {lc(cur['title'])}. {cur['story']}")
    if fed and fed.get("meetings"):
        last = fed["meetings"][-1]
        now.append(f"Futures price about {abs(last['cum_bp']) / 25:.1f} more {'hikes' if last['cum_bp'] > 0 else 'cuts'} by {_month(last['date'])}.")
    plans, sent = svk.get("capex_plans"), svk.get("sentiment")
    if plans and sent:
        now.append(f"Businesses are investing, with Philadelphia Fed capex plans at {plans['now']:.0f} versus an average of {plans['avg']:.0f}, "
                   f"while consumers are {'gloomy' if not sent['strong'] else 'upbeat'}, with Michigan sentiment at {sent['now']:.0f} versus {sent['avg']:.0f}.")
    fis = []
    ind = {x["key"]: x for x in (dc or {}).get("indicators", [])}
    if ind.get("debt_gdp"):
        fis.append(f"Federal debt held by the public is {ind['debt_gdp']['now']:.0f}% of GDP")
    if ind.get("int_rev"):
        fis.append(f"interest now takes {ind['int_rev']['now']:.0f}% of federal revenue")
    if dc:
        st, _, rest = dc["stage"].partition(", ")
        fis.append(f"Ray Dalio's framework puts the US in the {st[0].lower() + st[1:]} of the long-term debt cycle" + (f", {rest}" if rest else ""))
    paras = [move, path, " ".join(now), (_cap("; ".join(fis)) + ".") if fis else ""]
    labels = ["The move", "The chapters", "Where we are now", "Fiscal backdrop"]
    keys = [e for e in big if e is not cur][:2] + ([cur] if cur else [])
    bottom = (f"Over {yrs} years the 10-year is {abs(d10):.0f}bp {'higher' if d10 > 0 else 'lower'}, a path set by "
              + _join([lc(e["title"]) for e in keys]) + ".")
    return {"bottom_line": bottom, "paras": [{"label": l, "text": p} for l, p in zip(labels, paras) if p]}


# ---------------------------------------------------------------------------
# Executive summary: 3-5 sentences. Headline = direction + curve bias + cause + driver; then why the driver matters.
# ---------------------------------------------------------------------------
BIAS_PAST = {"Bear flattener": "bear-flattened", "Bear steepener": "bear-steepened", "Bull steepener": "bull-steepened",
             "Bull flattener": "bull-flattened", "Twist flattener": "twist-flattened", "Twist steepener": "twist-steepened",
             "Parallel bear shift": "shifted higher", "Parallel bull shift": "shifted lower", "Little changed": "held steady"}
BIAS = {"Bear flattener": "bear-flattening", "Bear steepener": "bear-steepening", "Bull steepener": "bull-steepening",
        "Bull flattener": "bull-flattening", "Twist flattener": "twist-flattening", "Twist steepener": "twist-steepening",
        "Parallel bear shift": "parallel", "Parallel bull shift": "parallel", "Little changed": "flat"}


def summary(a, mode, tr, cross, regime_1y, fed, k, moves, sv, themes, eps, auc, hn):
    T = {t["tenor"]: t for t in a["tenors"]}
    past, asof = date.fromisoformat(a["past"]), date.fromisoformat(a["asof"])
    rows = {r["key"]: r for r in tr["rows"]}
    d2, d10, d30 = (T[x]["chg_bp"] or 0 for x in ("2Y", "10Y", "30Y"))
    regime = a["regime"]
    bias = BIAS.get(regime, "mixed")
    when = WHEN.get(hn, f"since {_day(past)}, {past.year}")
    sold = (d2 + d10 + d30) / 3 > 0
    front_led = abs(d2) > abs(d30)
    svk = {s["key"]: s for s in sv}
    cpi, core, oil, jgb, u = k.get("cpi"), k.get("core_cpi"), k.get("oil"), k.get("jgb10"), k.get("unrate")
    cpi_chg = cpi["now"]["value"] - cpi["then"]["value"] if cpi and cpi.get("then") and cpi["then"]["period"] != cpi["now"]["period"] else 0
    oil_chg = oil["now"]["value"] / oil["then"]["value"] - 1 if oil and oil.get("then") else 0
    jgb_chg = jgb["now"]["value"] - jgb["then"]["value"] if jgb and jgb.get("then") else 0
    u_chg = u["now"]["value"] - u["then"]["value"] if u and u.get("then") else 0
    real, be = rows.get("real10"), rows.get("be10")
    hikes = [(d, bp) for d, bp in moves if bp > 0]
    cuts = [(d, bp) for d, bp in moves if bp < 0]
    it = svk.get("it_invest")
    hot = it and it["now"] >= 6
    tkeys = [t["key"] for t in (themes or []) if t.get("volume")][:2]
    spx = next((c for c in cross if c["sym"] == "^GSPC"), None)
    lv10 = (tr["levels"] or {}).get("10Y") or {}
    lvl = (f", its {'highest' if d10 > 0 else 'lowest'} since {_month(lv10['date'])}"
           if lv10.get("date") and (asof - date.fromisoformat(lv10["date"])).days > 365 else "")
    nums = (f"The 2-year {'rose' if d2 > 0 else 'fell'} {abs(d2):.0f}bp to {T['2Y']['today']:.2f}% and the 10-year "
            f"{'rose' if d10 > 0 else 'fell'} {abs(d10):.0f}bp to {T['10Y']['today']:.2f}%{lvl}")
    fwd = ""
    if fed and fed.get("meetings"):
        last, m = fed["meetings"][-1], fed["meetings"][0]
        fwd = (f"Futures now price about {abs(last['cum_bp']) / 25:.1f} {'hikes' if last['cum_bp'] > 0 else 'cuts'} by "
               f"{_month(last['date'])}")
        nxt = sorted([(m["date"], f"the FOMC on {_day(m['date'])}")] +
                     [(x["auction_date"], f"the {_sec(x['security'])} auction on {_day(x['auction_date'])}")
                      for x in ((auc or {}).get("coupons") or [])[:1]])
        fwd += f"; the next tests are {_join([t for _, t in nxt])}."

    # ---- long windows ----
    if mode != "near":
        yrs = round((asof - past).days / 365.25)
        same = [e for e in eps if e.get("d10") is not None and (e["d10"] > 0) == (d10 > 0)]
        big = max(same, key=lambda e: abs(e["d10"])) if same else None
        cur = eps[-1] if eps else None
        ls = rows["10Y"].get("largest_since") or {}
        if mode == "secular":
            head = (f"Over {yrs} years Treasuries {'sold off' if sold else 'rallied'} with a {bias} bias, the result of decades "
                    f"of falling inflation and rates" + (f" (most of all during the {lc(big['title'])})" if big and not sold and not lc(big['title']).startswith(("the ", "an ", "a ")) else f" (most of all during {lc(big['title'])})" if big and not sold else "")
                    + ("" if sold else ", partly reversed since the post-COVID inflation shock") + ".")
        else:
            head = (f"Over {yrs} years Treasuries {'sold off' if sold else 'rallied'} with a {bias} bias, driven above all by "
                    f"{lc(big['title'])} ({big['from'][:4]}–{big['to'][2:4]}), when {lc(big['channel'])}." if big else
                    f"Over {yrs} years Treasuries {'sold off' if sold else 'rallied'} with a {bias} bias.")
        s2 = (f"The 10-year went from {T['10Y']['past']:.2f}% to {T['10Y']['today']:.2f}%"
              + (f", the largest {yrs}-year {'rise' if d10 > 0 else 'fall'} since {ls['date'][:4]}" if ls.get("date") and yrs <= 10 else "")
              + f", and the 2-year from {T['2Y']['past']:.2f}% to {T['2Y']['today']:.2f}%.")
        s3 = (f"Today's chapter is {lc(cur['title'])}: {regime_1y and ('over the past year the curve has ' + BIAS_PAST.get(regime_1y, 'moved') + ' as the market priced a Fed leaning against a hot economy') or 'see the narrative below'}."
              if cur and cur is not big else "")
        return {"headline": head, "sentences": [x for x in (s2, s3, fwd) if x]}

    # ---- noise ----
    if tr["grade"]["label"] == "Noise":
        head = (f"Treasuries were little changed {when}, "
                + (f"with a slight {bias} bias " if bias not in ("parallel", "flat") else "in a roughly parallel move ")
                + f"that sits well inside normal ranges "
                f"(10-year {d10:+.0f}bp, 2-year {d2:+.0f}bp).")
        s = []
        if cpi_chg:
            s.append(f"The one data point that mattered was {_period(cpi['now']['period'])} CPI at {cpi['now']['value']:.1f}%"
                     + (f", lifted by energy while core held at {core['now']['value']:.1f}%, which kept rate-hike pricing intact"
                        if core and cpi["now"]["value"] - core["now"]["value"] >= 0.5 else "") + ".")
        if regime_1y:
            s.append(f"The bigger picture is unchanged: over the past year the curve has {BIAS_PAST.get(regime_1y, 'moved')}"
                     + (" as the market priced a Fed leaning against a hot economy." if regime_1y in ("Bear flattener", "Twist flattener") else "."))
        if fwd:
            s.append(fwd)
        return {"headline": head, "sentences": s}

    # ---- a real move: cause and driver ----
    infl_up = cpi_chg >= 0.3 or oil_chg >= 0.15
    infl_dn = cpi_chg <= -0.3 or oil_chg <= -0.15
    if sold and front_led:
        if infl_up:
            cause = "rising inflation concerns"
            x = "an oil shock" if oil_chg >= 0.15 else "firmer inflation data"
        elif hot:
            cause, x = "a hotter economy", "the AI investment boom"
        else:
            cause, x = "a more hawkish Fed", None
    elif sold:
        if jgb_chg >= 0.2 or "global" in tkeys:
            cause, x = "investors demanding more to hold duration", "a global bond selloff"
        elif be and real and be["chg_bp"] > real["chg_bp"]:
            cause, x = "rising long-run inflation concerns", "higher inflation expectations"
        else:
            cause, x = "investors demanding more to hold duration", "stronger growth and heavy supply"
    elif front_led:
        if infl_dn:
            cause, x = "expectations of Fed cuts", "cooling inflation"
        elif u_chg >= 0.2:
            cause, x = "expectations of Fed cuts", "a softening labor market"
        else:
            cause, x = "expectations of Fed cuts", None
    else:
        cause = "a bid for long bonds"
        x = "a risk-off move in equities" if spx and spx["chg"] < 0 and (spx.get("z") or 0) <= -0.5 else None
    verb = "were mixed" if regime.startswith("Twist") else "sold off" if sold else "rallied"
    if x:
        head = f"Treasuries {verb} {when} with a {bias} bias on {cause}, driven by {x}."
    else:
        tn = THEME_NOUN.get(tkeys[0]) if tkeys else None
        head = (f"Treasuries {verb} {when} with a {bias} bias on {cause}, without a single macro catalyst"
                + (f"; news flow centred on {tn}." if tn else "."))

    # Why the driver matters: the chain from the event to this part of the curve.
    why = ""
    fed_txt = (f"the Fed reversed course with a {sum(bp for _, bp in hikes)}bp hike in {_period(hikes[-1][0].strftime('%b %Y'))}" if hikes and cuts else
               f"the Fed hiked {sum(bp for _, bp in hikes)}bp in {_period(hikes[-1][0].strftime('%b %Y'))}" if hikes else
               f"the Fed cut {-sum(bp for _, bp in cuts)}bp" if cuts else "markets repriced the Fed")
    if not x:
        pass
    elif x == "an oil shock":
        why = (f"Oil's jump from ${oil['then']['value']:.0f} to ${oil['now']['value']:.0f} a barrel pushed headline CPI "
               f"{'from ' + format(cpi['then']['value'], '.1f') + '% to ' + format(cpi['now']['value'], '.1f') + '% ' if cpi_chg else ''}"
               + ("just as an AI investment boom kept the economy running hot, " if hot else "")
               + f"leaving no room to ease: {fed_txt}, and the front end, which trades the Fed, repriced most.")
    elif x == "firmer inflation data":
        why = (f"Headline CPI rose from {cpi['then']['value']:.1f}% to {cpi['now']['value']:.1f}%, which pushed out any easing: "
               f"{fed_txt}, and the front end, which trades the Fed, repriced most.")
    elif x == "the AI investment boom":
        why = (f"Business spending on computers, software and data centers is up {it['now']:.0f}% on the year, which keeps growth "
               f"and hiring firm; with the economy that strong, {fed_txt} and the front end repriced most.")
    elif x == "a global bond selloff":
        why = ("When long-term yields rise in Japan and Europe, global investors can earn more at home, so they demand a higher "
               "yield to hold long Treasuries; that lifted the long end more than the front"
               + (f", even as {fed_txt}." if hikes or cuts else "."))
    elif x == "higher inflation expectations":
        why = (f"10-year breakevens rose {be['chg_bp']:.0f}bp, so investors are asking for more compensation for future inflation, "
               "which shows up first at the long end.")
    elif x == "cooling inflation":
        why = ("Softer inflation gives the Fed room to ease, and the front end, which trades the Fed, rallied most.")
    elif x == "a softening labor market":
        why = (f"Unemployment rose from {u['then']['value']:.1f}% to {u['now']['value']:.1f}%, which raises the odds the Fed cuts "
               "to protect jobs, so the front end rallied most.")
    elif x and "risk-off" in x:
        why = ("Equities sold off and investors moved into the safety of long Treasuries, pulling long-term yields down most.")
    rb = real["chg_bp"] if real else None
    mix = ""
    if rb is not None and be and abs(d10) >= 8 and abs(rb) >= 2 * abs(be["chg_bp"]):
        mix = ("; nearly all of it came through real yields, so this is a repricing of the Fed's path rather than a loss of faith "
               "in long-run inflation control" if rb > 0 else "; nearly all of it came through real yields, a growth and Fed story")
    s3 = nums + mix + "."
    return {"headline": head, "sentences": [x_ for x_ in (why, s3, fwd) if x_]}


def _first(t):
    i = t.find(". ")
    s = t if i < 0 else t[:i]
    return s[:1].lower() + s[1:] + "." if not s[:2].isupper() else s + "."
