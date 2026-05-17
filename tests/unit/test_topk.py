from __future__ import annotations

from backend.core.algorithms.topk import stable_topk


def test_stable_topk_matches_full_sort_prefix() -> None:
    rows = [
        {"symbol": "c", "score": 0.9},
        {"symbol": "a", "score": 0.9},
        {"symbol": "b", "score": 0.8},
        {"symbol": "d", "score": 0.7},
    ]

    key = lambda row: (-float(row["score"]), str(row["symbol"]))

    assert stable_topk(rows, 2, key=key) == sorted(rows, key=key)[:2]


def test_stable_topk_handles_zero_and_overlarge_k() -> None:
    rows = [{"symbol": "b"}, {"symbol": "a"}]

    assert stable_topk(rows, 0, key=lambda row: row["symbol"]) == []
    assert stable_topk(rows, 10, key=lambda row: row["symbol"]) == [
        {"symbol": "a"},
        {"symbol": "b"},
    ]
