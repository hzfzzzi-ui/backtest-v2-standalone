# adaptive-regime-strategy

## MODIFIED Requirements

### Requirement: Regime-router-only product contract

The V2 product contract MUST no longer accept `ADAPTIVE_REGIME` as a runnable
strategy identifier in workbench execution or backend strategy construction.

Deprecated `adaptive_regime` compatibility behavior MAY remain in archived
artifacts and historical documentation, but the live product/runtime path MUST
require `REGIME_ROUTER`.

#### Scenario: Experiment API rejects removed strategy pack
- **WHEN** a workbench request uses `strategy_pack = ADAPTIVE_REGIME`
- **THEN** `_experiment_runner_api.py` MUST reject the request with a clear
  migration error pointing to `REGIME_ROUTER`

#### Scenario: Registry rejects removed strategy name
- **WHEN** backend runtime code or a script attempts to build
  `StrategyConfig(name="adaptive_regime")`
- **THEN** `registry.build_strategy()` MUST raise a clear error telling callers
  to use `regime_router`

#### Scenario: Frontend load does not silently execute removed compatibility path
- **WHEN** the frontend loads a saved config whose strategy is
  `ADAPTIVE_REGIME`
- **THEN** the UI MUST avoid preserving it as a loaded-clean executable config
  and MUST surface that the strategy has been removed
