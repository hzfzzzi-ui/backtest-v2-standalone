## Why

全样本差分已经证明，当前主线变弱的核心责任状态是 `TRANS_UP`。恢复态门控放松后，个股腿确实能重建仓位，但新增恢复态仓位的交易质量明显不够，导致 `PRE_PROFIT_BREAKOUT_FAILURE_EXIT`、`RISK_OFF_EXIT` 和 `ATR_STOP_LOSS` 显著增加，需要对恢复态 entry 质量做最小收口。

## What Changes

- 新增一个仅作用于 `TRANS_UP + benchmark_off` 恢复态旁路的 entry 质量过滤开关。
- 复用现有 `residual_strength_score` 和 `breakout_margin_score`，不新造评分体系。
- 仅过滤 `alpha_source = breakout / pullback_overlap`，不影响 `pullback_only`。
- 增强恢复态质量过滤的 diagnostics，便于 A/B 归因。

## Capabilities

### New Capabilities
- `trans-up-recovery-entry-quality-filter`: 定义恢复态 benchmark gate 旁路下的最小质量过滤合同与可观测性。

### Modified Capabilities
- `cn-stock-trend-alpha-core`: 个股 alpha sleeve 在 `TRANS_UP` 恢复态允许重建仓位时，增加可选的质量过滤收口。
- `api-runtime-config-compilation`: runtime 编译链需要支持恢复态质量过滤配置字段。

## Impact

- `backend/core/stage_pipeline/adapters/signal_postprocess.py`
- `backend/core/config/models.py`
- `backend/api/backtest_v2/semantic_config_schema.py`
- `backend/api/backtest_v2/semantic_config_compiler.py`
- `backend/api/backtest_v2/runner_config_risk_exit.py`
- `backend/core/engine_vector/signal_provider.py`
- `tests/unit/test_bridge_adapter_route_control.py`
- `tests/unit/test_semantic_config_compiler.py`
