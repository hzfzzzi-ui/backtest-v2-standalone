from __future__ import annotations

from datetime import date

import pandas as pd


def calendar_from_dates(dates: pd.Series, start: date, end: date) -> pd.DatetimeIndex:
    d = pd.to_datetime(dates).dt.normalize()
    d = d[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))]
    return pd.DatetimeIndex(sorted(set(d.tolist())))
