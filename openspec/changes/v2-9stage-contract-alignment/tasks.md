# Tasks: v2-9stage-contract-alignment

- [x] Build an S1-S9 alignment matrix covering frontend, validation/summary surfaces, API compiler, engine/runtime, and preview/report layers
- [x] Identify frontend-only fields and label them `未实现`
- [x] Identify backend-supported but frontend-missing fields and add them to the correct stage panels
- [x] Align S1 validation semantics with actual universe-resolution behavior or label it explicitly as sample-only
- [x] Classify the disposition of `signal_composition` and other ghost/non-stage surfaces
- [x] Resolve the known initial mismatch backlog (`RSI_REVERSAL`, `breadth`, `weight_mode`, `min_positions`, breakout advanced params, `ma20_exit`, `low10_exit`, `universe_filter.min_price`, `benchmark_regime`)
- [x] Normalize stage field names and compatibility aliases across draft/config/preview/report schemas
- [x] Verify each stage change against baseline experiment `exp_20260307_051743747_77d8`
- [x] Document remaining research-only or intentionally hidden fields outside the 9-stage contract
