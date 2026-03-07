# Design: Momentum Ranking (Top 10%)

## Approach

Replace the existing 4-factor scoring with a simple 3-factor momentum score: `20d_return + 60d_return + 120d_return`. Change selection from topN to top percentage.

## Changes

### 1. Score computation — `portfolio_simulator_strict.py` / `sma_signal_provider.py`

Replace `_build_daily_multifactor_scores()` internals:

```python
def _build_daily_multifactor_scores(candidates, mx, i, bench_close, ...):
    for sym in candidates:
        col = sym_to_col[sym]
        close = mx.close[:i+1, col]
        # 3-factor momentum
        roc20 = (close[-1] / close[-21] - 1) if len(close) > 20 else np.nan
        roc60 = (close[-1] / close[-61] - 1) if len(close) > 60 else np.nan
        roc120 = (close[-1] / close[-121] - 1) if len(close) > 120 else np.nan
        score = np.nanmean([roc20, roc60, roc120])  # average of available factors
        scores[sym] = score
```

### 2. Selection — `portfolio_builder.py`

Change `mf_topk` from absolute count to percentage:

```python
# Old: top_n = min(mf_topk, len(scored_candidates))
# New: top_n = max(1, int(len(scored_candidates) * momentum_top_pct))
```

Add `momentum_top_pct: float = 0.10` parameter.

### 3. Config

- `momentum_top_pct: float = 0.10` — top 10% of eligible stocks pass
- Keep `mf_topk` as a fallback maximum (if top 10% > mf_topk, cap at mf_topk)

### 4. Backward compatibility

When `momentum_top_pct = 0` or `enable_multifactor_rank = False`, behavior unchanged.
