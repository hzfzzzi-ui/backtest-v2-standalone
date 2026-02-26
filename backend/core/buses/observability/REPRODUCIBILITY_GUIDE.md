# Reproducibility Guide - Backtest V2

## Overview

The reproducibility system ensures that **same config + same seed = same results**, critical for:
- ✅ Validating strategy performance
- ✅ Debugging issues
- ✅ Regulatory compliance
- ✅ Team collaboration
- ✅ Research integrity

## Quick Start

### Basic Usage

```python
from backtest_v2.buses.observability import create_run_context
from backtest_v2.core.engine import run_backtest

# 1. Create run context (handles all reproducibility)
with create_run_context(config, output_dir="results", random_seed=42) as ctx:
    # 2. Run backtest (uses ctx.logger for structured logging)
    result = run_backtest(config, provider, strategy)

    # 3. Save results (auto-checksums)
    ctx.save_results(
        equity_curve=result.snapshots_to_df(),
        trades=result.ledger.trades_df(),
        signals=result.signals,
        summary=result.summary,
    )

# 4. Output automatically saved to:
# results/run_20250223_153045_a1b2c3d4/
#   ├── run_meta.json          # Complete metadata
#   ├── audit_log.jsonl        # Structured logs
#   ├── equity_curve.parquet   # Daily snapshots
#   ├── trades.parquet         # All trades
#   ├── signals.json           # All signals
#   └── summary.json           # Performance metrics
```

## run_meta.json Schema

### Complete Metadata Example

```json
{
  "run_id": "run_20250223_153045_a1b2c3d4",
  "run_timestamp": "2025-02-23T15:30:45.123Z",

  "git_commit": "fb45643abc123...",
  "code_checksum": "sha256:...",

  "config_hash": "c4ca4238a0b923820dcc509a6f75849b",
  "config_snapshot": {
    "initial_capital": 1000000,
    "universe": {
      "symbols": ["600000.sh", "600016.sh"],
      "start": "2023-01-01",
      "end": "2024-12-31"
    },
    "strategy": {
      "name": "MultifactorSignal",
      "buy_threshold": 50.0,
      "sell_threshold": 30.0
    }
  },

  "data_version": "v2.1.5",
  "data_as_of_date": "2025-02-23",
  "ohlcv_checksum": "e4d909c290d0fb1ca068ffaddf22cbd0",
  "universe_checksum": "098f6bcd4621d373cade4e832627b4f6",

  "python_version": "3.11.5",
  "dependencies": {
    "numpy": "1.24.3",
    "pandas": "2.0.3",
    "psycopg2": "2.9.6"
  },

  "random_seed": 42,

  "queries_executed": [
    {
      "query": "SELECT * FROM pit_ohlcv WHERE symbol IN (...) ORDER BY symbol, trade_date",
      "timestamp": "2025-02-23T15:30:46Z",
      "row_count": 50000
    }
  ],

  "equity_curve_checksum": "5d41402abc4b2a76b9719d911017c592",
  "trades_checksum": "7d793037a0760186574b0282f2f435e7"
}
```

### Key Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `run_id` | Unique identifier | `"run_20250223_153045_a1b2c3d4"` |
| `git_commit` | Code version | `"fb45643abc..."` |
| `config_hash` | Config fingerprint | SHA256 hash |
| `random_seed` | Reproducibility seed | `42` |
| `equity_curve_checksum` | Results fingerprint | SHA256 of equity values |
| `trades_checksum` | Trade log fingerprint | SHA256 of trade_id + amounts |

## Determinism Guarantees

### What's Guaranteed

✅ **Exact Equity Curve** - Same equity values to 6 decimal places
✅ **Exact Trades** - Same entry/exit prices, dates, P&L
✅ **Exact Signals** - Same signals generated on same dates
✅ **Exact Order Flow** - Same order submissions and fills

### What's NOT Guaranteed

❌ **Timestamps in audit_log.jsonl** - Varies by execution time
❌ **Execution duration** - Varies by system load
❌ **File creation timestamps** - Filesystem metadata

## Reproducibility Verification

### Compare Two Runs

```python
from backtest_v2.buses.observability import BacktestRunContext

# Run 1
with create_run_context(config, random_seed=42) as ctx1:
    result1 = run_backtest(config, provider, strategy)
    ctx1.save_results(...)

# Run 2
with create_run_context(config, random_seed=42) as ctx2:
    result2 = run_backtest(config, provider, strategy)
    ctx2.save_results(...)

# Verify
verification = ctx2.verify_reproducibility(ctx1.run_dir / "run_meta.json")

if verification["all_checks_pass"]:
    print("✅ Results are reproducible!")
else:
    print("❌ Results differ:")
    for check, passed in verification.items():
        if not passed:
            print(f"   - {check}: FAILED")
```

### Automated Verification Script

```bash
#!/bin/bash
# verify_reproducibility.sh

# Run backtest twice
python run_backtest.py --config configs/test.yaml --seed 42 --output results/run1
python run_backtest.py --config configs/test.yaml --seed 42 --output results/run2

# Compare checksums
python tools/compare_results.py results/run1/run_meta.json results/run2/run_meta.json
```

## Determinism Checklist

Our implementation ensures determinism through:

### 1. ✅ Database Query Ordering
```python
# All queries use deterministic ORDER BY
cursor.execute("""
    SELECT * FROM pit_ohlcv
    WHERE symbol IN (...)
    ORDER BY symbol, trade_date  -- ✅ Deterministic
""")
```

### 2. ✅ Dict Iteration Order
```python
# Use sorted() when order matters
for symbol in sorted(positions.keys()):
    process_position(symbol)
```

### 3. ✅ Floating-Point Precision
```python
# Round before checksumming
equity_values = equity_curve["equity"].round(6).tolist()
checksum = hash_list(equity_values)
```

### 4. ✅ Random Number Generation
```python
# Set seeds at start
set_random_seeds(random_seed)  # Sets numpy.random.seed() and random.seed()
```

### 5. ✅ Timestamp-Based IDs
```python
# Use deterministic counters
order_id = 1
for signal in signals:
    order = Order(order_id=order_id, ...)
    order_id += 1  # ✅ Deterministic
```

### 6. ✅ Concurrent Execution
```python
# Disable parallelization for reproducible runs
config.enable_parallel = False  # Sequential execution only
```

### 7. ✅ Data Updates
```python
# Snapshot data_as_of_date
cursor.execute("""
    SELECT * FROM pit_ohlcv
    WHERE trade_date <= %s  -- ✅ Point-in-time snapshot
    ORDER BY symbol, trade_date
""", (data_as_of_date,))
```

## Best Practices

### 1. Always Use Run Context

```python
# ✅ GOOD - Automatic reproducibility
with create_run_context(config) as ctx:
    result = run_backtest(...)
    ctx.save_results(...)

# ❌ BAD - Manual bookkeeping, easy to forget
run_id = str(uuid.uuid4())
set_random_seeds(42)
result = run_backtest(...)
# Forgot to save run_meta.json!
```

### 2. Version Your Data

```python
# ✅ GOOD - Data version tracked
run_meta.data_version = "v2.1.5"
run_meta.data_as_of_date = "2025-02-23"

# ❌ BAD - Unknown data state
# Data could change between runs
```

### 3. Commit Before Important Runs

```bash
# ✅ GOOD - Code version recorded
git commit -am "Fix strategy bug"
python run_backtest.py --config production.yaml

# ❌ BAD - Uncommitted changes not tracked
# edit strategy.py
python run_backtest.py --config production.yaml
# run_meta.git_commit doesn't match actual code!
```

### 4. Use Named Seeds for Variants

```python
# ✅ GOOD - Systematic seed variation
for sensitivity in [10, 20, 30]:
    seed = 42 + sensitivity  # Deterministic seed variation
    with create_run_context(config, random_seed=seed) as ctx:
        run_backtest(...)

# ❌ BAD - Random seed variation
import random
for i in range(10):
    seed = random.randint(1, 10000)  # Not reproducible!
```

## Troubleshooting

### Problem: Results Don't Match

**Symptoms**: `equity_curve_checksum` differs between runs

**Diagnosis**:
1. Check if config changed:
   ```python
   # Compare config_hash
   assert run1_meta.config_hash == run2_meta.config_hash
   ```

2. Check if data changed:
   ```python
   # Compare ohlcv_checksum
   assert run1_meta.ohlcv_checksum == run2_meta.ohlcv_checksum
   ```

3. Check if code changed:
   ```python
   # Compare git_commit
   assert run1_meta.git_commit == run2_meta.git_commit
   ```

4. Check for non-determinism:
   ```bash
   # Run 10 times with same seed, compare all
   for i in {1..10}; do
     python run_backtest.py --seed 42 --output run_$i
   done
   python tools/verify_all_match.py run_*
   ```

### Problem: Git Commit Shows "unknown"

**Cause**: Not in a git repository or git not installed

**Solution**:
```bash
# Initialize git if needed
git init
git add .
git commit -m "Initial commit"
```

### Problem: Database Query Not Deterministic

**Cause**: Missing `ORDER BY` clause

**Solution**:
```python
# ✅ Add ORDER BY to all queries
cursor.execute("""
    SELECT symbol, trade_date, close
    FROM pit_ohlcv
    WHERE ...
    ORDER BY symbol, trade_date  -- Critical!
""")
```

## Advanced Usage

### Custom Checksums

```python
# Add custom checksums to run_meta
with create_run_context(config) as ctx:
    result = run_backtest(...)

    # Add custom checksum
    custom_data = compute_custom_metric(result)
    ctx.run_meta.config_snapshot["custom_metric_checksum"] = hash_dict(custom_data)

    ctx.save_results(...)
```

### Audit Query Trail

```python
# Track all database queries
class AuditingDataProvider(DataProvider):
    def load_ohlcv_daily(self, symbols, start, end, source):
        query = f"SELECT * FROM {source} WHERE symbol IN (...)"
        result = self.execute(query)

        # Record query
        self.query_audit.append({
            "query": query,
            "timestamp": datetime.now(UTC).isoformat(),
            "row_count": len(result),
        })

        return result

# Attach to run_meta
ctx.run_meta.queries_executed = provider.query_audit
```

### Parallel Runs for Sensitivity Analysis

```python
from concurrent.futures import ProcessPoolExecutor

configs = generate_sensitivity_configs(base_config)

def run_with_context(config_seed_tuple):
    config, seed = config_seed_tuple
    with create_run_context(config, random_seed=seed) as ctx:
        result = run_backtest(config, provider, strategy)
        ctx.save_results(...)
    return ctx.run_id

# Run in parallel (each process gets deterministic seed)
with ProcessPoolExecutor(max_workers=4) as executor:
    run_ids = list(executor.map(run_with_context, configs))

# All runs reproducible individually
```

## Integration with Frontend

The frontend can display reproducibility status:

```javascript
// Load run_meta.json
fetch('/api/backtest/results/run_20250223/run_meta.json')
  .then(r => r.json())
  .then(meta => {
    // Display version info
    document.getElementById('git-commit').textContent = meta.git_commit.substring(0, 8);
    document.getElementById('random-seed').textContent = meta.random_seed;

    // Show checksums (for verification)
    document.getElementById('equity-checksum').textContent = meta.equity_curve_checksum.substring(0, 16);
  });
```

## Summary

| Feature | Status | Benefit |
|---------|--------|---------|
| run_meta.json | ✅ | Complete metadata capture |
| Deterministic seeds | ✅ | Exact reproducibility |
| Result checksumming | ✅ | Quick verification |
| Query audit trail | ✅ | Data provenance |
| Context manager | ✅ | Automatic bookkeeping |
| Git tracking | ✅ | Code version control |
| Verification tools | ✅ | Easy comparison |

**Next**: Use `create_run_context()` in all backtest scripts for automatic reproducibility!
