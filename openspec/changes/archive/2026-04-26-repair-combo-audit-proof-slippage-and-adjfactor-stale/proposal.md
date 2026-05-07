## Why

当前组合主线在三个关键审计点上还不够可信：

1. 组合层 `timing_alignment` / `universe_lineage` 无法把 stock sleeve 的 `PIT_DYNAMIC` 与 `NEXT_OPEN` 证据正式聚合到组合 audit，导致组合层审计经常停在 `UNKNOWN`。
2. `costs.slippage_mode` 已有正式配置，但 stage-pipeline fill 逻辑没有真实消费，配置语义与运行时行为漂移。
3. `adj_factor` 当前会被静默前向填充，但没有 stale 风险审计，组合层无法对复权链的新鲜度给出 `PASS/WARN/FAIL`。

这些问题优先级高于继续做收益实验，因为它们直接影响系统的可信、可审计和可复现。

## What Changes

- 为组合 audit 增加 component-level 证明链聚合，让组合层显式继承 stock / ETF 组件的 `timing_alignment` 与 `universe_lineage` 证据。
- 在 stage-pipeline 成交记账路径正式实现 `slippage_mode = price_adjustment_only | cost_only` 的运行时语义。
- 在 data bundle 中新增 `adj_factor` stale 统计，并在 research audit 中新增对应 gate。

## Capabilities

### New Capabilities
- `combo-audit-proof-aggregation`: 组合层正式聚合 stock / ETF component 的 PIT 与 NEXT_OPEN 证据。
- `adj-factor-stale-audit`: 对复权因子的 stale 前向填充风险输出正式审计结果。

### Modified Capabilities
- `stage-pipeline-fill-accounting`: 正式消费 `slippage_mode` 配置，避免成本模型配置语义漂移。

## Impact

- 影响代码：
  - `backend/core/audit/research_audit.py`
  - `backend/core/stage_pipeline/adapters/runtime_state.py`
  - `backend/core/stage_pipeline/adapters/bridge_adapter.py`
  - `backend/core/stage_pipeline/adapters/fill_accounting.py`
  - `backend/core/tools/data_bundle_builder.py`
- 影响测试：
  - `tests/unit/test_research_audit_contract.py`
  - `tests/unit/test_bridge_adapter_accounting.py`
  - `tests/unit/test_data_bundle_builder.py`
- 不改组合预算逻辑，不改 stock / ETF 策略逻辑，不改 baseline 选股/选 ETF 结果。
