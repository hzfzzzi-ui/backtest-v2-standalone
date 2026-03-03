# Protocol Contract Migration Plan (N ~ N+2)

## Scope
- Canonical artifact filename: `reason_codes.csv`
- Canonical counters: `raw_signal`, `blocked`, `orders`, `skipped`, `closed_trades`
- `symbol_performance.csv` becomes required (empty file allowed)

## Timeline
- Version N: write canonical only; read supports canonical + legacy aliases.
- Version N+1: keep read compatibility; track legacy-hit metrics in API/run_meta.
- Version N+2: remove legacy readers (`reason_code_counts.csv` and `*_count` counter aliases).

## Observability
- `run_meta.legacy_hits.reason_codes_filename`
- `run_meta.legacy_hits.counters_field_alias`
- Execution preview response includes aggregated `legacy_hits`.

## Rollback
- If N rollout causes regressions, re-enable legacy fallback readers only (no dual-write).
- Do not change canonical write path during rollback to avoid creating new drift.

## Ownership
- Backend: maintain protocol constants and compatibility window.
- Frontend: keep canonical UI display, with internal fallback only during compatibility window.
- QA: validate both canonical contract tests and legacy compatibility tests each release.
