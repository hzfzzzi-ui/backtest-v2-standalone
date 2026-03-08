# Baseline Regression Contract (2026-03-07)

This runbook lives under `docs/ops/` because it governs operator validation,
not product behavior.

## Locked baseline

The single accepted cleanup baseline is:

- `exp_id = exp_20260307_051743747_77d8`
- artifacts root: `outputs/experiments/exp_20260307_051743747_77d8`
- saved config id: `cfg_d5bcddc928d1`
- saved config hash: `c3dc319e5924398921ce66c4b7abdcf5290fdf82`
- saved config source: `baseline / manual / locked=true`
- draft hash captured with the baseline request: `d12f819e5d4ed5a751968f8bcb7e3267c82b388bfd197459e34a9488aedf32d0`
- baseline `config_conflict_policy`: `config_id_overrides_workbench`

This baseline is an experiment artifact set plus a resolved input bundle. It is not a built-in preset alias.

## Baseline facts

### Runtime / universe

- universe mode: `HS300_ZZ500`
- symbols source: `pit_index_constituents`
- index code: `000906.SH`
- benchmark: `000300.SH`
- date range: `2016-03-01 .. 2026-03-01`
- raw symbols: `800`
- tradable symbols: `519`
- after filters: `519`
- resolve as-of: `2016-03-01`
- price adjustment: `hfq`
- engine mode: `VECTOR_FAST_STRICT`
- execution profile: `tradable`

### Performance

- total return: `0.8087501044202998`
- CAGR: `0.0635482026379195`
- max drawdown: `-0.47180753475805515`
- sharpe: `0.3638706027515262`
- calmar: `0.13469094483729954`
- trades: `61`
- turnover: `0.0022975841800369537`

### Artifact facts

- `run_config` hash: `a3345867f40cf9e61ab3afe49e0b00c44efd94910bcbc2ac917277c26deadb59`
- `nav.csv` rows: `2424`
- `nav.csv` first row: `2016-03-01, 1000000.0`
- `nav.csv` last row: `2026-02-13, 1808750.1044203`
- `portfolio_trades.csv` rows: `61`
- trade reason distribution:
  - `BREAKOUT_HIGH = 34`
  - `ATR_STOP_LOSS = 14`
  - `ATR_TRAIL_EXIT = 13`

## Required comparison set

Each cleanup change must compare the candidate experiment against the locked baseline using:

- `run_config.json`
- `run_meta.json` semantic core
- `perf.json`
- `nav.csv`
- `portfolio_trades.csv`
- `report.html` semantic summary

The comparison is implemented by [baseline_regression_check.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/baseline_regression_check.py).

## Equality policy

### Blocking checks

These produce `FAIL`:

- `run_config.json` semantic equality
- `perf.json` metric equality
- `run_meta.json` semantic core equality
- `run_meta.universe` equality
- `nav.csv` equality via row-count, endpoints, and file hash
- `portfolio_trades.csv` equality via row-count, reason distribution, and file hash
- `report.html` summary semantics equality

### Diagnostic-only checks

These produce `WARN` but not `FAIL`:

- saved-config provenance drift
- `config_conflict_policy` drift
- report source-diagnostic drift when summary semantics still match

This split exists so cleanup can distinguish result drift from metadata/reporting drift. `WARN` still requires explicit acknowledgment in the change notes.

## Status classification

- `PASS`: no mismatches
- `WARN`: only diagnostic-only mismatches
- `FAIL`: at least one blocking mismatch

Mismatch categories:

- `code_drift`
- `saved_config_resolution_drift`
- `database_universe_data_drift`
- `report_rendering_drift`
- `report_diagnostic_drift`

## Operator workflow

### 1. Self-check the locked baseline

```powershell
python backend/scripts/baseline_regression_check.py
```

Expected result: `PASS`.

### 2. Compare an existing candidate experiment

```powershell
python backend/scripts/baseline_regression_check.py --candidate-exp-id exp_YYYYMMDD_xxxxxx
```

### 3. Rerun the baseline through current code

Run this inside the backtest runtime container so DB/service resolution matches production:

```powershell
docker exec backtest-v2-standalone python /app/backend/scripts/baseline_regression_check.py --rerun
```

The script reconstructs the baseline request from the locked experiment bundle, launches a fresh run, then compares the new experiment artifacts back to the baseline.

### 4. Persist a machine-readable result

```powershell
python backend/scripts/baseline_regression_check.py --candidate-exp-id exp_YYYYMMDD_xxxxxx --output-json outputs/execution/baseline_regression_latest.json
```

## Current verification status

Validated on `2026-03-07`:

- self-compare of `exp_20260307_051743747_77d8` returns `PASS`
- current code can rerun the baseline request and compare the new experiment through the same script

Future cleanup changes should record the comparison outcome in their implementation notes before proceeding to the next stage.
