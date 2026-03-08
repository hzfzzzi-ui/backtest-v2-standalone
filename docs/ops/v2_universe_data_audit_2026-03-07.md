# V2 Universe Data Audit (2026-03-07)

This document records the verified universe data lineage after the
`v2-universe-data-audit` change.

It now lives under `docs/ops/` because it is an operator audit artifact rather
than product documentation.

## Baseline

Locked baseline experiment:
- `exp_20260307_051743747_77d8`

Baseline universe facts:
- `universe_mode = HS300_ZZ500`
- `symbols_source = pit_index_constituents`
- `index_code = 000906.SH`
- `resolve_asof = 2016-03-01`
- `raw_count = 800`
- `tradable_symbols = 519`
- `after_filters_symbols = 519`

This means baseline safety depends directly on the `pit_index_constituents`
rows for `000906.SH`.

## Runtime lineage by universe mode

| Mode | Runtime source | `resolve_asof` policy | Dynamic entry | Import dependency |
| --- | --- | --- | --- | --- |
| `ALL_A` | `pit_security_master + pams_ohlcv_daily` | end date | yes | none |
| `HS300_ZZ500` | `pit_index_constituents` (`000906.SH`) | start date | no | CSI800 PIT import |
| `CSI1000` | `pit_index_constituents` (`000852.SH`) | start date | no | CSI1000 PIT import |
| `INDUSTRY` | `pit_industry_history` | start date | no | industry ingest |
| `CUSTOM` | user input | request-local | no | none |

Key distinction:
- `ALL_A` does not consume `pit_index_constituents`
- `HS300_ZZ500` and `CSI1000` do consume `pit_index_constituents`, but by
  different `index_code` values

## Validation-path contract

`/api/backtest_v2/validate_data` now follows the same universe timing semantics
as runtime execution:
- `ALL_A` resolves at end date and reports `dynamic_all_a_entry = true`
- index and industry modes resolve at start date
- `CUSTOM` validates exactly the provided symbols

This route is therefore a runtime-universe validation path, not a sample-symbol
placeholder for non-`CUSTOM` modes.

## Import-chain audit

### CSI800

Relevant assets:
- `backend/scripts/fetch_csi800_pit.py`
- `backend/scripts/import_csi800_pit.py`
- `backend/core/universe/ingest_universe.py --index`
- `data_cache/csi800_pit_changes.csv`
- `data_cache/csi800_pit_snapshots.csv`
- legacy static snapshot: `data_cache/index_stock_cons_000906.csv`

Current safe behavior:
- CSI800 imports now replace only `index_code = '000906.SH'`
- they no longer wipe the entire `pit_index_constituents` table

### CSI1000

Relevant assets:
- `backend/scripts/fetch_csi1000_pit.py`
- `backend/scripts/fetch_csi1000_pit_monthly.py`
- `backend/scripts/import_csi1000_pit.py`
- `data_cache/csi1000_pit_changes.csv`
- `data_cache/csi1000_pit_monthly_changes.csv`
- `data_cache/csi1000_pit_monthly_snapshots.csv`

Quality note:
- `fetch_csi1000_pit.py` produces a static fallback dataset
- `fetch_csi1000_pit_monthly.py` is the higher-fidelity PIT path

## Redundant or ambiguous assets

These are cleanup candidates, not immediate deletion targets:

- `data_cache/index_stock_cons_000906.csv`
  - static CSI800 snapshot from the older `ingest_universe --index` path
  - lower fidelity than `csi800_pit_changes.csv`

- `backend/core/universe/ingest_universe.py --index`
  - still valid as a CSI800-only loader
  - historically implied full-table replacement, which was misleading once
    `CSI1000` also depended on `pit_index_constituents`

- `backend/scripts/fetch_csi1000_pit.py`
  - usable fallback
  - should not be treated as equivalent to monthly PIT reconstruction

## Script-driven workflow impact

Search and research scripts currently split across:
- `HS300_ZZ500` matrix-search and champion-style scripts
- `ALL_A` workbench-derived experiment generators

Implication:
- cleanup of CSI constituent imports must be validated against both the
  baseline `HS300_ZZ500` path and `ALL_A` scripts that do not consume those
  imports at runtime

## Safe cleanup plan

1. Keep `pit_index_constituents` as a shared table for multiple index codes.
2. Never use CSI800 import paths that replace the whole table.
3. Treat `ALL_A` as independent from CSI constituent imports.
4. Prefer monthly-reconstructed PIT datasets over static snapshots for
   baseline-sensitive index universes.
5. Defer deletion of redundant cache files until script users confirm they no
   longer rely on them.
