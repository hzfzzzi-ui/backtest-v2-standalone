## Final Cleanup Review

Date: 2026-03-15
Change: `cleanup-final-v10-1-architecture-debt`

### Regression anchor

- baseline: `baseline_V10_1`
- linked experiment: `exp_20260314_144548534_7db9`

Confirmed snapshot:

- `total_return = 4.425630011081876`
- `max_drawdown = -0.29025259513173496`
- `cagr = 0.2032763161631579`
- `sharpe = 0.8891097010317657`
- `calmar = 0.7003428033809594`
- `turnover = 0.02077596030035478`
- `orders = 467`
- `closed_trades = 230`

### Architecture-debt items closed in this change

#### API surface

- desktop main path no longer depends on `/api/backtest_v2/artifacts/read`
- runtime path no longer keeps historical artifact alias / counter alias normalization
- `configs_impl.py` was reduced to a thin route layer
- `semantic_config_compiler.py` no longer mixes schema models and compiler logic in one file

Relevant files:

- `backend/api/backtest_v2/runner_impl.py`
- `backend/api/backtest_v2/artifacts_impl.py`
- `backend/api/backtest_v2/configs_impl.py`
- `backend/api/backtest_v2/semantic_config_compiler.py`
- `backend/api/backtest_v2/semantic_config_schema.py`
- `backend/api/backtest_v2/builtin_config_library.py`

#### Frontend results owner and provenance

- production results surface is Vue-only
- fallback DOM owner is removed from the main path
- old `input_source_*` / `loaded_source_*` state naming is gone from frontend source files
- source provenance is now explicit auxiliary state, while runtime truth is carried by:
  - `runtime_source_kind`
  - `runtime_source_id`
  - `active_manifest`
  - `active_surface_summary`

Relevant files:

- `frontend/assets/js/backtest_v2.js`
- `frontend/assets/js/ui-controls.js`
- `frontend/assets/js/artifacts.js`
- `frontend/assets/js/state/workbench-state.js`
- `frontend/assets/js/state/active-experiment-state.js`
- `frontend/assets/js/state/config-draft-core.js`

#### Research entry governance

- top-level `run*_research.py` count: `0`
- study definitions under `research/studies/*.study.yaml`: `14`
- generated thin scripts under `backend/scripts/generated/*.py`: `14` active entries plus `__init__.py`
- outdated diagnostic / sweep / validation research entry points were removed from the top-level surface

Relevant files:

- `backend/research/thin_script.py`
- `backend/scripts/inventory.json`
- `backend/scripts/README.md`

### Static debt checks after cleanup

Zero-hit checks in main source:

- `/api/backtest_v2/artifacts/read`
- `wbResultsFallbackRoot`
- `setDesktopFallbackMode`
- `isDesktopFallbackModeEnabled`
- `input_source_`
- `loaded_source_`
- `legacy_config_id`
- `load_exp_id`

Top-level script checks:

- `backend/scripts/run*_research.py` count = `0`

### Remaining files that are still large but no longer counted as cleanup debt

These remain large and deserve future modularization, but they are now treated as behavior-sensitive hotspots rather than lingering architecture debt:

- `backend/core/engine_vector/breakout_signal_provider.py`
- `backend/core/engine_vector/strict_runtime_impl.py`
- `backend/core/engine_vector/regime_router_signal_provider.py`
- `backend/api/backtest_v2/runner_impl.py`
- `backend/api/backtest_v2/semantic_config_compiler.py`
- `frontend/assets/js/ui-controls.js`
- `frontend/assets/js/backtest_v2.js`

Conclusion:

The cleanup debt targeted by this change is closed. What remains is not compatibility residue; it is ordinary large-file modularization work that must be handled under behavior-preservation discipline.
