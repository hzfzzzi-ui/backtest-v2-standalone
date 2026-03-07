# Design: Universe Price Filter

## Approach

Add `min_price` field to `UniverseFilterConfig` and apply it in `apply_universe_filters()`.

## Changes

### 1. Config — `backend/core/universe/hs300_csi500.py`

```python
@dataclass(frozen=True)
class UniverseFilterConfig:
    exclude_st: bool = True
    exclude_suspended: bool = True
    min_list_days: int = 120
    min_avg_turnover_20d: float = 1e8
    exclude_limit_lock: bool = False
    min_price: float = 5.0          # NEW
```

### 2. Filter logic — `apply_universe_filters()`

After the turnover check, add:
```python
if cfg.min_price > 0 and row.get("last_close", 0) < cfg.min_price:
    reasons.append("EXCLUDE_LOW_PRICE")
```

`last_close` needs to be populated in `build_candidates_from_ohlcv()` from the latest close price per symbol.

### 3. Candidate builder — `build_candidates_from_ohlcv()`

Add `last_close` field to the candidate dict:
```python
"last_close": float(sym_df["close"].iloc[-1])
```

### 4. Engine integration

The engine calls `apply_universe_filters()` before building matrices. The price filter naturally flows through without additional engine changes.

## No changes needed
- `data_matrix.py` — tradable flag unchanged
- API — UniverseFilterConfig serialized via `**kwargs`
- Frontend — deferred to later (Stage tab restructure)
