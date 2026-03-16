## Why

当前 `daily_accounting.py`、`artifacts_diagnostics.py` 和 `strict_runtime_daily_loop.py` 仍然同时承载执行本体、阶段计数和诊断口径，导致计数语义容易随内部执行重构一起漂移。现在需要把诊断 owner 从执行 owner 中剥离，后续继续拆 runtime 热点时才能保持 `baseline_V10.1` 口径稳定。

## What Changes

- 新增统一的 runtime diagnostics snapshot / stage count contract，明确哪些计数属于执行层原始事件，哪些计数属于诊断层归一化口径。
- 将 `daily_accounting.py` 收口为“执行日快照 + 原始诊断输入”提供者，不再直接定义最终 buy funnel 阶段语义。
- 将 `artifacts_diagnostics.py` 收口为“canonical diagnostics builder”，统一产出 buy funnel、reason counters 和 surface diagnostics。
- 收缩 `strict_runtime_daily_loop.py` 的职责，只保留执行主循环与原始事件汇总，不再承担最终诊断口径归一化。
- 对 `baseline_V10.1 -> exp_20260314_144548534_7db9` 建立更明确的 smoke 门，确保拆层不改变收益、回撤、订单数、交易数和关键 stage diagnostics。

## Capabilities

### New Capabilities
- `runtime-diagnostic-accounting`: 定义执行日快照、原始诊断输入和 canonical stage count 的统一契约。

### Modified Capabilities
- `core-hotspot-modularization`: 约束 default runtime daily loop 与 stage accounting 在模块化后不得继续混合执行行为与诊断口径。
- `artifact-finalization-pipeline`: 要求 diagnostics/funnel 构建只消费 canonical runtime diagnostics snapshot，不再直接依赖执行本体细节。
- `execution-shell-unification`: 要求正式执行总线中的 diagnostics adapter 成为唯一计数归一化层，执行 facade 不得重新承担最终诊断 owner。

## Impact

- 影响代码：
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/api/backtest_v2/artifacts_diagnostics.py`
  - `backend/core/engine_vector/strict_runtime_daily_loop.py`
  - 相关 diagnostics / artifact / smoke tests
- 不改：
  - `V10.1` 信号时点
  - 成交时点
  - 收益/回撤/订单/交易基线
- 风险集中在 stage 计数、buy funnel 和 reason diagnostics 的口径对齐，需要用 baseline smoke 和 artifact compare 锁死。
