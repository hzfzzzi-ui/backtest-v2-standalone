from __future__ import annotations

from datetime import date


def next_trading_day(calendar: list[date], day: date) -> date | None:
    try:
        i = calendar.index(day)
    except ValueError:
        return None
    return calendar[i + 1] if i + 1 < len(calendar) else None
