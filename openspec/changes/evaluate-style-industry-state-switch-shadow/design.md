## Context

The repository already contains the raw pieces needed for state-switch
diagnosis:

- market-level state inputs:
  - weekly five-state regime logic
  - formal regime blocks: trend, risk, breadth, participation
- style index coverage in `pit_index_daily`:
  - `000300.SH` (`HS300`)
  - `000905.SH` (`ZZ500`)
  - `000852.SH` (`CSI1000`)
- industry lineage and SW L1 index mapping:
  - `pit_industry_history`
  - `SW_L1_INDEX_MAP`
  - `pit_index_daily` SW L1 index rows
- existing read-only attribution outputs:
  - held exposure
  - candidate pressure
  - cash-block reason
  - industry/theme alignment

The missing piece is a unified daily state surface that uses those inputs
without changing runtime semantics.

## Design

### M1. Market Style State

The runner computes a daily `style_state` panel from index history. The first
version uses:

- broad benchmark:
  - `000300.SH`
- style comparators:
  - `000905.SH`
  - `000852.SH`

Daily features per style index:

- `ret20`, `ret60`
- `close_vs_ma20`
- `ma20_vs_ma60`
- `drawdown20`, `drawdown60`
- `vol20`

Cross-style relative features:

- `ret20_500_minus_300`
- `ret20_1000_minus_300`
- `ret20_1000_minus_500`
- optional normalized trend-score spread equivalents

Derived labels:

- `broad_bull`
- `large_cap_defense`
- `mid_small_beta`
- `split_rotation`
- `risk_off`

The panel must also persist the raw component scores, not only the label, so
later runtime ABs can be traced back to the evidence.

### I1. Industry Health

The runner computes a daily SW L1 `industry_health` panel from SW L1 index
history and stock exposure/candidate context.

Per industry daily features:

- `proxy_ret20`, `proxy_ret60`, `proxy_ret120`
- `close_vs_ma20`, `ma20_vs_ma60`
- `drawdown20`, `drawdown60`
- `vol20`
- cross-industry `rank_pct`

Optional exposure-aware features when source artifacts exist:

- `held_exposure_pct`
- `held_position_count`
- `candidate_rows`
- `selected_rows`
- `cash_blocked_rows`

Daily labels:

- `healthy`
- `watch`
- `confirmed_weak`

The first version should use state transitions with persistence, not a pure
single-day threshold:

- `healthy -> watch` when weakness flags reach watch count
- `watch -> confirmed_weak` when weakness persists or intensifies
- `confirmed_weak -> healthy` only after explicit recovery confirmation

### R1. Rotation Pressure

The runner computes a daily explanation layer that joins the above states to the
stock sleeve:

- `holding_industry_pressure`:
  weighted weakness of currently held industries
- `candidate_industry_pull`:
  weighted strength of top candidate industries
- `blocked_rotation_gap`:
  strength of industries that had candidate pressure but were not entered due to
  `SKIP_NO_CASH` or capacity limits

This layer is diagnostic only. It should answer:

1. Did market style already rotate?
2. Were current holdings still concentrated in weakening industries?
3. Were stronger industries visible in candidates?
4. Were they blocked by old holdings or cash limits?

## Scope Boundary

This change stops at research-only shadow outputs. It does not yet:

- sell weak-industry holdings earlier;
- protect new-style candidates;
- swap holdings across industries;
- alter benchmark regime, five-state regime, or account state.

Those require a later separate L3 runtime AB.

## Risks

- Style labels can become noisy if based on one-day relative moves. The runner
  must keep persistence and raw scores visible.
- Industry health can overfit if too many dimensions are combined at once. The
  first version should stay close to trend, drawdown, rank, and observed sleeve
  pressure.
- Old windows may have partial coverage for some SW legacy index mappings. The
  runner must mark coverage quality explicitly and avoid baseline-upgrade claims.
