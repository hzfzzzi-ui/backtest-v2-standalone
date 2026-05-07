## Why

`band_rerank` already proved that monthly moneyflow can change candidate boundaries and materially improve the `1217` window while improving drawdown quality in `1226`.

The next minimal question is whether the rerank should stay active in all states, or only in stronger states:

- `BULL`
- `BULL + TRANS_UP`

This change tests state gating without changing the factor source, band size, or baseline shell.

## What Changes

- add two explicit moneyflow overlay modes:
  - `bull_only_band_rerank`
  - `bull_trans_up_band_rerank`
- gate `band_rerank` activation by market state only
- add a new minimal study `v10/moneyflow_monthly_band_rerank_state_gate_s1`
- compare `B0`, `MF_BAND20_BULL`, and `MF_BAND20_BULL_TRANSUP`

## Impact

- affected code:
  - `backend/core/engine_vector/factor_insertion_contracts.py`
  - `backend/core/portfolio/candidate_plan.py`
  - tests / study files
- default live baseline behavior remains unchanged
