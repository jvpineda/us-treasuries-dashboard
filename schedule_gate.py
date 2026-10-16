"""Should the scheduled job publish now? Prints "true" or "false".

Publish once per trading day, as soon as possible after 8:30am New York time (the morning economic releases).
GitHub may start scheduled jobs late, so the workflow runs several times each morning; each run publishes only if
today is a trading day, it is past 8:30am in New York, and the live site has not already been built since then.
"""
from __future__ import annotations

import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

import sources as S
from trading_day import is_trading_day

NY = ZoneInfo("America/New_York")
SITES = ["https://ustdashboard.vercel.app/data/meta.json",
         "https://jvpineda.github.io/us-treasuries-dashboard/data/meta.json"]
RELEASES = time(8, 30)


def last_built():
    """Most recent build time across the published sites (None if none can be read)."""
    out = []
    for url in SITES:
        try:
            meta = json.loads(S.http_get(f"{url}?t={datetime.now().timestamp():.0f}", timeout=15))
            out.append(datetime.fromisoformat(meta["built_at"]).astimezone(NY))
        except Exception:
            pass
    return min(out) if out else None  # the oldest site decides, so a lagging copy still gets refreshed


def should_publish(now=None):
    now = now or datetime.now(NY)
    if not is_trading_day(now.date()) or now.time() < RELEASES:
        return False, f"{now:%a %H:%M} NY: not a trading day or before 8:30am"
    built = last_built()
    cutoff = datetime.combine(now.date(), RELEASES, NY)
    if built and built >= cutoff:
        return False, f"already published today at {built:%H:%M} NY"
    return True, f"last build {built:%a %b %d %H:%M} NY" if built else "no published build found"


if __name__ == "__main__":
    ok, why = should_publish()
    print(why, file=__import__("sys").stderr)
    print("true" if ok else "false")
