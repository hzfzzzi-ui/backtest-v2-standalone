## Core Hotspot Split Plan

Date: 2026-03-15
Regression anchor: `baseline_V10_1 -> exp_20260314_144548534_7db9`

### Scope

This note defines the remaining file-level split boundaries for high-risk `backend/core` hotspots. It is intentionally structural: it does not authorize execution-timing changes, fill-policy changes, or strategy-behavior changes.

### Current hotspot sizes

- `backend/core/engine_vector/breakout_signal_provider.py`: 2287 lines
- `backend/core/engine_vector/strict_runtime_impl.py`: 2130 lines
- `backend/core/engine_vector/regime_router_signal_provider.py`: 920 lines
- `backend/core/services/market_snapshot_service.py`: 873 lines
- `backend/core/portfolio/portfolio_builder.py`: 842 lines
- `backend/core/engine_vector/multi_alpha_signal_provider.py`: 639 lines

### Already completed in this change

- `portfolio_builder.py`
  - extracted scoring helpers into `backend/core/portfolio/selection_scoring.py`
- `market_snapshot_service.py`
  - extracted normalization/formatting helpers into `backend/core/services/market_snapshot_utils.py`
- `multi_alpha_signal_provider.py`
  - extracted shared helpers into `backend/core/engine_vector/multi_alpha_common.py`
- `strict_runtime_impl.py`
  - reused extracted multifactor helper from `backend/core/engine_vector/multifactor_rank.py`

### Remaining split boundary for `breakout_signal_provider.py`

Keep in file:
- provider lifecycle
- route-specific decision flow
- day-level orchestration that directly affects signal timing

Eligible future extracts:
- candidate quality scoring helpers
- pullback-variant normalization helpers
- diagnostic row formatting helpers
- breakout margin/fade/open-gap pure scorers

Must not change:
- decision bar semantics
- `t+1` execution assumptions
- exit trigger ordering
- baseline ranking/selection behavior

### Remaining split boundary for `strict_runtime_impl.py`

Keep in file:
- runtime loop orchestration
- stage ordering
- portfolio mutation sequencing
- result assembly order

Eligible future extracts:
- pure request normalization
- per-day audit row builders
- result payload formatters
- multifactor / score-weight preparation helpers
- non-mutating summary calculators

Must not change:
- trade execution timing
- fill accounting order
- counter semantics
- performance aggregation semantics

### Remaining split boundary for `regime_router_signal_provider.py`

Keep in file:
- actual regime routing behavior
- strategy-state transitions

Eligible future extracts:
- state reset helpers
- benchmark/regime precompute helpers
- ATR lookup preparation
- per-mode diagnostic formatters

Deferred for safety:
- `_day_signals_trend`
- `_day_signals_mr`
- `_day_signals_light`
- `_day_signals_exits_only`
- `_day_signals_perstock`

Reason:
- these methods are behavior-dense and tightly coupled to runtime timing; extraction should happen in smaller verified slices only after a dedicated regression loop.

### Guardrail

Every future split of these files must re-check:

- `total_return`
- `max_drawdown`
- `cagr`
- `sharpe`
- `calmar`
- `turnover`
- `orders`
- `closed_trades`

against `baseline_V10_1 -> exp_20260314_144548534_7db9`.
