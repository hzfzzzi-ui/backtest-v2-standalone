from __future__ import annotations

from collections import deque
from math import isnan
from typing import Iterable

import numpy as np


def rolling_mean_1d(values: Iterable[float], window: int) -> np.ndarray:
    w = int(window)
    arr = [float(v) if v is not None else float("nan") for v in values]
    out = np.full(len(arr), np.nan, dtype=float)
    if w <= 0:
        return out
    q: deque[float] = deque()
    running = 0.0
    valid_count = 0
    for idx, value in enumerate(arr):
        q.append(value)
        if not isnan(value):
            running += value
            valid_count += 1
        if len(q) > w:
            old = q.popleft()
            if not isnan(old):
                running -= old
                valid_count -= 1
        if len(q) == w and valid_count == w:
            out[idx] = running / float(w)
    return out


def rolling_max_1d(values: Iterable[float], window: int) -> np.ndarray:
    return _rolling_extreme_1d(values, window, find_max=True)


def rolling_min_1d(values: Iterable[float], window: int) -> np.ndarray:
    return _rolling_extreme_1d(values, window, find_max=False)


def _rolling_extreme_1d(values: Iterable[float], window: int, *, find_max: bool) -> np.ndarray:
    w = int(window)
    arr = [float(v) if v is not None else float("nan") for v in values]
    out = np.full(len(arr), np.nan, dtype=float)
    if w <= 0:
        return out
    q: deque[tuple[int, float]] = deque()
    valid_window: deque[bool] = deque()
    valid_count = 0
    for idx, value in enumerate(arr):
        valid = not isnan(value)
        valid_window.append(valid)
        if valid:
            valid_count += 1
            while q and ((q[-1][1] <= value) if find_max else (q[-1][1] >= value)):
                q.pop()
            q.append((idx, value))
        if len(valid_window) > w:
            old_valid = valid_window.popleft()
            if old_valid:
                valid_count -= 1
        min_idx = idx - w + 1
        while q and q[0][0] < min_idx:
            q.popleft()
        if idx + 1 >= w and valid_count == w and q:
            out[idx] = q[0][1]
    return out


def rolling_mean_matrix_streaming(values: np.ndarray, window: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("rolling matrix input must be 2D")
    out = np.full(matrix.shape, np.nan, dtype=float)
    for col in range(matrix.shape[1]):
        out[:, col] = rolling_mean_1d(matrix[:, col], int(window))
    return out
