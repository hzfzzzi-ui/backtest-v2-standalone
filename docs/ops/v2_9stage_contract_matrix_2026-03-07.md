# V2 9-Stage Contract Matrix (2026-03-07)

This matrix now lives under `docs/ops/` because it is a maintenance contract
reference, not end-user documentation.

Baseline contract reference:
- experiment: `exp_20260307_051743747_77d8`
- baseline source config: `cfg_d5bcddc928d1`

Columns:
- `FE`: frontend control exists in the 9-stage drawer
- `Validate/Summary`: surfaced in S1 validate, summary bar, or adjacent user-facing diagnostics
- `API`: `_experiment_runner_api.py` consumes / compiles the field
- `Runtime`: engine / runner actually consumes the compiled field
- `Preview/Report`: visible in execution preview, report, or artifact readback
- `Status`: `supported | unimplemented | research-only`

| Stage | Contract surface | FE | Validate/Summary | API | Runtime | Preview/Report | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 Universe | `universe_mode`, `industries`, `symbols`, `limit`, `filters` | yes | yes | yes | yes | yes | supported | `validate_data` now uses real resolver for non-`CUSTOM` modes |
| S2 Market regime | `regime_detection`, `benchmark_regime` | yes | yes | yes | yes | yes | supported | `benchmark_regime` is now visible in summary and report |
| S3 Industry gate | `sector_gate` | yes | summary only | yes | yes | yes | supported | `signal_composition` kept in stage area but marked `未实现` |
| S4 Stock trend | `stock_trend_filter` | yes | summary only | yes | yes | yes | supported | runtime fallback alias remains `enable_v2_trend_filter` |
| S5 Ranking | `ranking.momentum_top_pct` | yes | summary only | yes | yes | yes | supported | multifactor / strength ranking remain outside 9-stage |
| S6 Entry | `EMA/SMA/BREAKOUT`, breakout advanced params, MR arm | yes | yes | yes | yes | yes | supported / partial | `RSI_REVERSAL` as main strategy is explicitly `未实现`; MR arm is supported inside `REGIME_ROUTER` |
| S7 Portfolio | `max_positions`, `portfolio_mode`, `weight_mode`, `min_positions` | yes | yes | yes | yes | yes | supported | `weight_mode` / `min_positions` are now first-class UI fields |
| S8 Risk | `risk_budget`, `market_filter`, `breadth` | yes | yes | yes | yes | yes | supported / partial | `Risk Gate` remains `未实现` and disabled |
| S9 Exit | `signal_reverse`, ATR stop / trail, time exit, take profit, fixed stop, `ma20_exit`, `low10_exit`, hold constraints | yes | yes | yes | yes | yes | supported | `MA20_EXIT` and `LOW10_EXIT` are now visible in UI and report |

## Ghost / Non-Stage Surfaces

| Surface | Disposition | Reason |
| --- | --- | --- |
| `signal_composition.modules` | research-only | still serialized in draft / diff for comparison, but main experiment compiler does not consume it |
| `RSI_REVERSAL` main strategy | unimplemented | registry exists, but main experiment compile map does not route it as a primary strategy |
| `Risk Gate` panel | unimplemented | visible only as disabled placeholder to avoid a false promise |
| S1 `price_max` | unimplemented | written into draft / report, but runtime universe filters only consume `min_price` |
| S1 `match_price` | unimplemented | workbench control exists, but main experiment execution still uses fixed `next_open` |
| S1 `limit_trade` | unimplemented | user-visible toggle exists, but runtime only consumes `limit_rule` |
| S1 `constituent_mode` | unimplemented | current resolver semantics are determined by `universe_mode`, not by a separate fixed/dynamic switch |
| S1 `industry_system` | unimplemented | current implementation is fixed to `pit_industry_history.industry_l1` |
| config diff / JSON panel | supported adjacent surface | explicitly tied to the compiled runtime config, not treated as a stage |
| execution preview config resolution | supported adjacent surface | now follows the same config-source governance rules as run execution |

## Remaining Intentionally Hidden Or Non-9-Stage Fields

These fields or controls remain outside the 9-stage contract on purpose:

- `strength rank`, `multifactor rank`, `mf_topk`, concentration knobs: still script / preview oriented
- `wbStrategyFamily`: legacy selector fallback used only to avoid breaking old layouts
- `wbSaveTemplate`, `wbSaveFlowScript`: config storage actions, not stage parameters
- `wbChartMode`, `wbSymbolFilter`, `wbSymbolSort`: chart / inspector controls, not workbench contract
- `wbHistoryCompare`, `wbHistoryCompareCount`, `wbCompareClose`: experiment comparison UI, not stage parameters
- `wbErrorBannerView`: error/status affordance, not stage parameters

## Explicit Compatibility Aliases

- `universe.filters.price_min` <-> `universe_filter.min_price`
- `stock_trend_filter.short_ma/long_ma` <-> runtime `v2_trend_short_ma/v2_trend_long_ma`
- `exit_rules.ma20_exit.enabled` <-> runtime `exit.enable_ma20_exit`
- `exit_rules.low10_exit.enabled` <-> runtime `exit.enable_low10_exit`
- `position_risk.portfolio_mode` <-> runtime strategy params `portfolio_mode`
- `sizing.weight_mode/min_positions` <-> runtime `sizing.weight_mode/min_positions`
- `benchmark_regime.*` remains top-level in workbench config and run config

## Known Gaps Left For Later Changes

- provider unification is deferred to `v2-engine-surface-cleanup`
- universe naming cleanup (`symbols_source`, `resolve_asof` semantics, CSI import audit) is deferred to `v2-universe-data-audit`
- baseline artifact gates stay owned by `v2-baseline-lock-and-regression`
