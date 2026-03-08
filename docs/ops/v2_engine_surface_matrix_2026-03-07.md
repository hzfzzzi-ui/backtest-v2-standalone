# V2 Engine Surface Matrix (2026-03-07)

This matrix now lives under `docs/ops/` because it documents maintenance and
support boundaries rather than product-facing behavior.

This document records the production runtime surface after the
`v2-engine-surface-cleanup` change.

## Product runtime contract

The product runtime contract is limited to strategy paths that are:
- reachable from the main workbench
- compilable by the experiment API
- exercised by baseline-safe execution

Current product-supported strategy names:
- `sma_cross`
- `ema_cross`
- `breakout_trend`
- `regime_router`

Removed compatibility alias:
- `adaptive_regime`
  - classification: `removed`
  - runtime behavior: live compiler and registry now reject it and require
    `regime_router`
  - implementation note: no standalone `adaptive_regime.py` runtime file remains

Research-only strategy names:
- `bollinger_breakout`
- `composite`
- `ma_atr_stop`
- `ma_trend_filter`
- `momentum_roc`
- `multifactor_signal`
- `relative_strength`
- `rsi_reversal`
- `sma_cross_regime`
- `sma_cross_regime_atr`
- `volume_breakout`

Notes:
- `rsi_reversal` remains reachable as the MR arm inside `regime_router`, but it
  is not a product-supported primary strategy.
- `composite` remains runtime-executable for research scripts, but it is not a
  workbench/API product feature.

## Provider protocol decision

Provider surfaces are explicitly classified as one of:
- `integrated`
- `isolated`
- `deprecated`

Current decision:

| Provider | Classification | Protocol status | Runtime entrypoint |
| --- | --- | --- | --- |
| `BreakoutTrendProvider` | `product-supported` | `integrated` | `_run_vector_portfolio_backtest_breakout` |
| `GenericSignalProvider` | `research-only` | `isolated` | none |
| `SMASignalProvider` | `research-only` | `isolated` | none |
| `RegimeRouterSignalProvider` | `research-only` | `isolated` | none |

Decision summary:
- `BreakoutTrendProvider` is the only provider integrated into the production
  runtime.
- Mainline SMA/EMA/RegimeRouter execution still uses the strict inline runtime.
- Generic/provider parity implementations stay available for research, but they
  do not define the supported production contract.

## Runtime routing

`run_vector_portfolio_backtest_strict()` now routes through a single local
route-resolution helper:
- `provider_breakout_runtime`
  - used for `BreakoutTrendStrategy`
- `generic_inline_runtime`
  - used for `CompositeStrategy`
- `strict_inline_runtime`
  - used for product SMA/EMA/RegimeRouter paths and all fallback research paths

This keeps current behavior while avoiding a separate transitional routing
module.

## Convergence targets

Duplicated engine logic was audited and classified instead of being deleted
blindly.

Current keep/remove decisions:
- keep `BreakoutTrendProvider` integrated in the production runtime
- keep the strict inline runtime as the product path for SMA/EMA/RegimeRouter
- keep `GenericSignalProvider`, `SMASignalProvider`, and
  `RegimeRouterSignalProvider` isolated as research-only implementations
- keep `CompositeStrategy` on the generic inline runtime for research parity
- remove `strategy_adapter` because it had no justified runtime or research-only consumer
- remove `runtime_surface.py` after folding its only runtime responsibility into
  `portfolio_simulator_strict.py`
- remove `adaptive_regime.py` and the live `adaptive_regime` compatibility
  branch because the supported contract now requires `regime_router`

This change intentionally stops short of rewriting the strict inline engine.
Future cleanup may either integrate additional providers or remove isolated
paths, but the current contract is now explicit.

## Script boundary

Research and matrix-search scripts may continue to use broader strategy and
provider surfaces than the product runtime. These scripts are allowed to exist
for experimentation, but they do not expand the supported product contract.

Examples:
- `backend/core/tools/compare_paths.py`
  - research-only parity harness
- matrix-search and sweep scripts under `backend/scripts/`
  - research-only unless explicitly wired into the workbench/API contract

## Coordination with dead-code cleanup

This change classifies surfaces before deleting them.

Implications:
- product-supported paths must not be removed by zero-reference cleanup
- research-only paths may be isolated without being deleted immediately
- deprecated paths should be deletion candidates only after no intended support
  classification depends on them
