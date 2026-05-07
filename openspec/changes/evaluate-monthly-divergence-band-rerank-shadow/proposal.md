## Why

`monthly_divergence_rate` has already shown research signal, but two weaker insertion modes did not close the gap to the live stock baseline shell:

- `bull_only_tiebreak` was connected but inert because no same-day base-score ties appeared.
- `soft_weight` changed sizing behavior, but it only reallocated capital inside the already planned buy set.

The next minimal question is whether moneyflow works better as a **candidate-band rerank**:

- keep the current residual baseline shell,
- preserve the baseline order outside a bounded candidate band,
- rerank only the top candidate band with monthly moneyflow scores,
- measure whether this produces a cleaner `B0 vs overlay` separation than pure sizing.

## What Changes

- add a new moneyflow overlay mode: `band_rerank`
- require an explicit `band_limit` contract when that mode is enabled
- rerank only the bounded candidate band, keeping the rest of the baseline ranking unchanged
- add a new minimal study `v10/moneyflow_monthly_band_rerank_s1`
- run the study on the formal `1217 / 1226` windows

## Impact

- affected code:
  - `backend/core/engine_vector/factor_insertion_contracts.py`
  - `backend/core/engine_vector/moneyflow_overlay.py`
  - `backend/core/portfolio/candidate_plan.py`
  - runtime plumbing / tests
- affected behavior:
  - only when `moneyflow_overlay.enabled = true` and `mode = band_rerank`
  - no change to the default live baseline behavior
