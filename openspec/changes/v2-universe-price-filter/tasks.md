# Tasks: v2-universe-price-filter

- [x] Add `min_price: float = 5.0` to `UniverseFilterConfig` in `backend/core/universe/hs300_csi500.py`
- [x] Add `last_close` field to candidate dict in `build_candidates_from_ohlcv()`
- [x] Add price filter check in `apply_universe_filters()` with reason `EXCLUDE_LOW_PRICE`
- [x] Verify engine integration — min_price wired through all 3 engine paths via `build_ohlc_matrices_from_history(min_price=)`
- [x] Add `min_price` parameter passthrough in API (`_experiment_runner_api.py`) + strategy dataclasses + registry builders
