# CSI1000 PIT Runbook

## Formal rebuild prerequisites

- Provide a versioned `data_cache/csi1000_rebalance_calendar.csv` that includes official scheduled and ad hoc effective dates.
- Set `TUSHARE_TOKEN` with access to `index_weight`, either in the process environment or repo `.env`.
- Confirm PostgreSQL target table `public.pit_index_constituents` is reachable.

## Formal rebuild commands

One-command refresh:

```bash
python backend/scripts/refresh_csi1000_pit.py \
  --calendar data_cache/csi1000_rebalance_calendar.csv \
  --provider tushare
```

Official/manual snapshot path:

```bash
python backend/scripts/refresh_csi1000_pit.py \
  --provider manual_manifest \
  --manual-manifest data_cache/csi1000_manual/manifest.csv
```

Equivalent split commands:

```bash
python backend/scripts/fetch_csi1000_pit_by_calendar.py \
  --calendar data_cache/csi1000_rebalance_calendar.csv \
  --provider tushare \
  --out-dir data_cache
```

```bash
python backend/scripts/import_csi1000_pit.py \
  --from-csv data_cache/csi1000_pit_calendar_changes.csv \
  --summary-out outputs/ops/csi1000_pit_import_summary.json
```

Manual split commands:

```bash
python backend/scripts/build_csi1000_pit_from_manual_snapshots.py \
  --manifest data_cache/csi1000_manual/manifest.csv \
  --out-dir data_cache/csi1000_manual \
  --summary-out outputs/ops/csi1000_pit_manual_build_summary.json
```

```bash
python backend/scripts/import_csi1000_pit.py \
  --from-csv data_cache/csi1000_manual/csi1000_pit_manual_changes.csv \
  --summary-out outputs/ops/csi1000_pit_import_summary.json
```

## Expected outputs

- `data_cache/csi1000_pit_calendar_snapshots.csv`
- `data_cache/csi1000_pit_calendar_changes.csv`
- `data_cache/csi1000_pit_calendar_summary.json`
- `outputs/ops/csi1000_pit_import_summary.json`

Manual path outputs:

- `data_cache/csi1000_manual/manifest.csv`
- `data_cache/csi1000_manual/csi1000_pit_manual_snapshots.csv`
- `data_cache/csi1000_manual/csi1000_pit_manual_changes.csv`
- `outputs/ops/csi1000_pit_manual_build_summary.json`

## Low-fidelity fallback

- Use `--allow-static-fallback` only for explicit emergency rebuilds or local debugging.
- A rebuild that uses `provider=akshare_static` or mixed static fallback events must not be treated as baseline-grade PIT history.
- Runtime will classify pure static fallback as `static_fallback` and block `CSI1000 + PIT_DYNAMIC` unless `universe.allow_low_fidelity_history=true`.

Example fallback command:

```bash
python backend/scripts/refresh_csi1000_pit.py \
  --calendar data_cache/csi1000_rebalance_calendar.csv \
  --provider akshare_static \
  --allow-static-fallback \
  --allow-count-mismatch
```

## Rollback

- Re-import the previous trusted `CSI1000` changes CSV with `backend/scripts/import_csi1000_pit.py`.
- If runtime investigation is required, set `universe.allow_low_fidelity_history=true` explicitly and treat outputs as non-baseline research only.
