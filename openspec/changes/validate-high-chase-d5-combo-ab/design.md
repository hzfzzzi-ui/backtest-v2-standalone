## Context

`CN_STOCK_ETF_COMBO_BASELINE_V3` is a unified stock+ETF combo result. Its `run_meta.dependencies.component_runs` shows:

- stock component: `exp_20260510_033603951_8649`
- ETF component: `exp_20260510_034150821_8962`

The combo runtime source of truth is the unified runtime/component source contract. This AB must rerun both sleeves through the normal runtime and assemble combo NAV from those generated component NAVs.

## Design

### Runner

Create a research runner mode: `cn_stock_etf_stock_rule_combo_ab`.

The runner builds each request by:

1. Loading the combo template workbench config from `outputs/baselines/CN_STOCK_ETF_COMBO_BASELINE_V3/config.json`.
2. Loading stock runtime config from `outputs/experiments/exp_20260510_033603951_8649/run_config.json`.
3. Loading ETF runtime config from `outputs/experiments/exp_20260510_034150821_8962/run_config.json`.
4. Applying the study window to combo, stock runtime, ETF runtime, and component semantic configs.
5. Applying only the variant's `stock_runtime_param_patch` to `stock_runtime.strategy.params`.
6. Injecting the stock and ETF runtime configs into `component_source_contract.components.*.compile_input.runtime_config`.
7. Removing stale execution contracts so the unified runtime rebuilds the execution contract from the patched component runtime inputs.
8. Running the result through `experiment_runtime_access.run_experiment_sync`.

### Variants

- `B0_COMBO_V3_REPLAY`: same combo template and same component runtime configs, window only.
- `HC_D5_IMMEDIATE_COMBO`: same as B0, but stock runtime enables:
  - `enable_mfe_mae_confirmation_exit=true`
  - `mfe_mae_confirmation_scope=high_chase`
  - `mfe_mae_confirmation_action=exit`
  - `mfe_mae_confirmation_lookahead_bars=3`
  - `mfe_mae_confirmation_min_mfe_pct=0.02`
  - `mfe_mae_confirmation_max_mae_pct=-0.05`
  - `mfe_mae_confirmation_exit_pct=0.5`

### Audit

The conclusion must compare B0 vs candidate by same window, not by unrelated baseline display layers. It must report combo metrics and component exp ids, and inspect stock component reason codes for `MFE_MAE_CONFIRMATION_EXIT`.

## Risks

- Rebuilding component execution contracts from runtime configs can differ from stale baseline execution-contract snapshots. Mitigation: B0 replay is included in the same study and is the decision anchor.
- ETF component reruns may have identical config but fresh exp ids. Mitigation: record ETF exp ids and compare ETF metrics/paths.
- Candidate may improve stock leg but be diluted by ETF sleeve or account allocator. Mitigation: report combo and stock component effects separately.
