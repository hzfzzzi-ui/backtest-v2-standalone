## Design

### Goal

Evaluate whether monthly moneyflow candidate-band rerank is more stable when constrained to stronger market states.

### Contract

`asset_context.moneyflow_overlay.mode` gains:

- `bull_only_band_rerank`
- `bull_trans_up_band_rerank`

Both modes:

- keep `factor_role = rank`
- keep the same `band_limit` contract as `band_rerank`
- reuse the same moneyflow snapshot source

### Runtime behavior

1. baseline ranking remains unchanged
2. when a state-gated band-rerank mode is enabled:
   - `bull_only_band_rerank` activates only in `BULL`
   - `bull_trans_up_band_rerank` activates in `BULL` and `TRANS_UP`
3. when the state gate is off:
   - overlay diagnostics can still exist
   - rerank behavior is suppressed

### Study shape

`v10/moneyflow_monthly_band_rerank_state_gate_s1` uses:

- `B0`
- `MF_BAND20_BULL`
- `MF_BAND20_BULL_TRANSUP`

on the same `1217 / 1226` windows as the prior band-rerank study.
