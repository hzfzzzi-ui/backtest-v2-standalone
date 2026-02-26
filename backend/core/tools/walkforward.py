from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class WFFold:
    fold_id: str
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def split_wf3(start: date, end: date) -> list[WFFold]:
    if start >= end:
        raise ValueError("start must be < end")
    total_days = (end - start).days + 1
    if total_days < 10:
        raise ValueError("range too short for wf3")

    def _mk(fold_id: str, train_ratio: float) -> WFFold:
        train_days = max(1, int(total_days * train_ratio))
        if train_days >= total_days:
            train_days = total_days - 1
        train_end = start + timedelta(days=train_days - 1)
        test_start = train_end + timedelta(days=1)
        return WFFold(
            fold_id=fold_id,
            train_start=start,
            train_end=train_end,
            test_start=test_start,
            test_end=end,
        )

    return [
        _mk("F1", 0.50),
        _mk("F2", 0.60),
        _mk("F3", 0.70),
    ]

