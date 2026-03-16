from __future__ import annotations

from typing import Any

import numpy as np


def cross_rank_pct(values: dict[str, float | None]) -> dict[str, float]:
    valid = [(key, float(value)) for key, value in values.items() if value is not None and not np.isnan(float(value))]
    out: dict[str, float] = {str(key): 0.0 for key in values.keys()}
    if len(valid) <= 1:
        for key, _ in valid:
            out[str(key)] = 0.5
        return out
    valid_sorted = sorted(valid, key=lambda item: item[1])
    denom = max(len(valid_sorted) - 1, 1)
    for idx, (key, _value) in enumerate(valid_sorted):
        out[str(key)] = float(idx) / float(denom)
    return out


def build_daily_multifactor_scores(
    *,
    i: int,
    day_cands: np.ndarray,
    symbols: list[str],
    close: np.ndarray,
    bench_close: np.ndarray,
    volume: np.ndarray | None = None,
    amt_matrix: np.ndarray | None = None,
) -> dict[str, float]:
    if int(len(day_cands)) < 5:
        return {str(symbols[int(c)]): 0.5 for c in day_cands}
    if amt_matrix is None and volume is None:
        raise ValueError("build_daily_multifactor_scores requires amt_matrix or volume")
    scores: dict[str, float] = {}
    if amt_matrix is not None:
        vol_raw: dict[str, float | None] = {}
        roc20_raw: dict[str, float | None] = {}
        rs60_raw: dict[str, float | None] = {}
        bb_raw: dict[str, float | None] = {}
        bench_now = float(bench_close[i]) if i < len(bench_close) and not np.isnan(bench_close[i]) else np.nan
        bench_60 = float(bench_close[i - 60]) if i - 60 >= 0 and not np.isnan(bench_close[i - 60]) else np.nan
        bench_roc60 = None
        if not np.isnan(bench_now) and not np.isnan(bench_60) and bench_60 > 0:
            bench_roc60 = float(bench_now / bench_60 - 1.0)
        for c in day_cands:
            col = int(c)
            sym = str(symbols[col])
            amt = amt_matrix[:, col]
            if i >= 19:
                w = amt[i - 19 : i + 1]
                w = w[~np.isnan(w)]
                if len(w) >= 20:
                    mu = float(np.mean(w))
                    sd = float(np.std(w))
                    v = float(amt[i]) if not np.isnan(amt[i]) else np.nan
                    vol_raw[sym] = ((v - mu) / sd) if (sd > 0 and not np.isnan(v)) else None
                else:
                    vol_raw[sym] = None
            else:
                vol_raw[sym] = None
            c_now = float(close[i, col]) if not np.isnan(close[i, col]) else np.nan
            c_20 = float(close[i - 20, col]) if i - 20 >= 0 and not np.isnan(close[i - 20, col]) else np.nan
            roc20_raw[sym] = (c_now / c_20 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_20) and c_20 > 0) else None
            c_60 = float(close[i - 60, col]) if i - 60 >= 0 and not np.isnan(close[i - 60, col]) else np.nan
            if not np.isnan(c_now) and not np.isnan(c_60) and c_60 > 0 and bench_roc60 is not None:
                rs60_raw[sym] = float(c_now / c_60 - 1.0) - float(bench_roc60)
            else:
                rs60_raw[sym] = None
            if i >= 19:
                cw = close[i - 19 : i + 1, col]
                cw = cw[~np.isnan(cw)]
                if len(cw) >= 20:
                    mid = float(np.mean(cw))
                    sd = float(np.std(cw))
                    up = mid + 2.0 * sd
                    dn = mid - 2.0 * sd
                    span = float(up - dn)
                    bb_raw[sym] = float((c_now - mid) / span) if (span > 0 and not np.isnan(c_now)) else None
                else:
                    bb_raw[sym] = None
            else:
                bb_raw[sym] = None
        r_vol = cross_rank_pct(vol_raw)
        r_roc = cross_rank_pct(roc20_raw)
        r_rs = cross_rank_pct(rs60_raw)
        r_bb = cross_rank_pct(bb_raw)
        for c in day_cands:
            sym = str(symbols[int(c)])
            scores[sym] = float(
                0.25 * r_vol.get(sym, 0.0)
                + 0.25 * r_roc.get(sym, 0.0)
                + 0.25 * r_rs.get(sym, 0.0)
                + 0.25 * r_bb.get(sym, 0.0)
            )
        return scores

    for c in day_cands:
        col = int(c)
        sym = str(symbols[col])
        c_now = float(close[i, col]) if not np.isnan(close[i, col]) else np.nan
        c_20 = float(close[i - 20, col]) if i - 20 >= 0 and not np.isnan(close[i - 20, col]) else np.nan
        roc20 = (c_now / c_20 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_20) and c_20 > 0) else np.nan
        c_60 = float(close[i - 60, col]) if i - 60 >= 0 and not np.isnan(close[i - 60, col]) else np.nan
        roc60 = (c_now / c_60 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_60) and c_60 > 0) else np.nan
        c_120 = float(close[i - 120, col]) if i - 120 >= 0 and not np.isnan(close[i - 120, col]) else np.nan
        roc120 = (c_now / c_120 - 1.0) if (not np.isnan(c_now) and not np.isnan(c_120) and c_120 > 0) else np.nan
        factors = [roc20, roc60, roc120]
        score = float(np.nanmean(factors))
        scores[sym] = score if not np.isnan(score) else 0.0
    return scores
