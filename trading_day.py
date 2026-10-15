"""Is today (New York time) a US Treasury market trading day?

    python3 trading_day.py             # prints "true" or "false"
    python3 trading_day.py 2026-11-11  # check a given date

Weekends and the full-day closes on SIFMA's recommended US bond market calendar are not trading days: New Year's
Day, Martin Luther King Jr. Day, Presidents Day, Good Friday, Memorial Day, Juneteenth, Independence Day, Labor
Day, Columbus Day, Veterans Day, Thanksgiving and Christmas. A holiday on a Saturday is observed the Friday before
(except New Year's Day, which SIFMA does not move back into December); one on a Sunday is observed the Monday after.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def _nth_weekday(year, month, weekday, n):
    """n-th given weekday of a month (n = -1 for the last)."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year):
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(d, new_year=False):
    if d.weekday() == 5:
        return None if new_year else d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def holidays(year):
    fixed = [_observed(date(year, 1, 1), new_year=True), _observed(date(year, 6, 19)), _observed(date(year, 7, 4)),
             _observed(date(year, 11, 11)), _observed(date(year, 12, 25))]
    floating = [_nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), _easter(year) - timedelta(days=2),
                _nth_weekday(year, 5, 0, -1), _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 10, 0, 2),
                _nth_weekday(year, 11, 3, 4)]
    return {d for d in fixed + floating if d}


def is_trading_day(d):
    return d.weekday() < 5 and d not in holidays(d.year)


if __name__ == "__main__":
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(ZoneInfo("America/New_York")).date()
    print("true" if is_trading_day(d) else "false")
