# Design: Industry Trend Gate (Top 30%)

## Approach

Compute daily 60d return for each of 31 SW L1 industry indices. Cross-sectional rank. Map each stock to its industry. Gate: only stocks in top 30% industries can be bought.

## Data Flow

```
pit_index_daily (31 sectors)
  → 60d return per sector per day
  → cross-sectional rank (1-31)
  → top 30% ≈ top 9 sectors
  → stock → sector mapping
  → sector_eligible[t, stock] bool matrix
```

## Changes

### 1. Sector return computation — new function in `features.py` or `regime_filter.py`

```python
def compute_sector_rankings(sector_data: pd.DataFrame, window: int = 60) -> dict:
    """Returns {date: {sector_code: rank}} where rank 1 = best."""
    for date in dates:
        returns = {}
        for sector in sectors:
            ret = close[date] / close[date - window] - 1
            returns[sector] = ret
        ranked = sorted(returns, key=returns.get, reverse=True)
        # top 30% = first ceil(31 * 0.3) = 10 sectors
```

### 2. Stock-to-sector mapping

Use `pit_security_master.industry_l1` or `SW_L1_INDEX_MAP` mapping. The mapping should be loaded once and is static (industry classification doesn't change frequently).

### 3. Gate integration — `signal_matrix.py` or provider `precompute()`

Build `sector_eligible` matrix (T×N bool). AND with buy signals:
```python
buy_signal = buy_base & sector_eligible
```

### 4. Engine paths

Must work in ALL paths (SMA, Generic, Breakout). Best approach: compute `sector_eligible` in `data_matrix.py` or `features.py` as a universal pre-filter, similar to `tradable`.

### 5. Data requirement

`load_sector_indices()` in `pg_provider.py` already loads sector OHLC. Need to ensure it's called and passed through to the feature computation layer.

### 6. Config

- `enable_sector_gate: bool = False`
- `sector_rank_window: int = 60`
- `sector_top_pct: float = 0.30`
