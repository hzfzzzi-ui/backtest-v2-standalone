## Why

当前 runtime 中的 `mf_rank` 已经不是纯 moneyflow rank：在当前实现里，它实际承载的是候选的 `final_score` 排序、topk 截断和仓位倾斜入口。继续沿用 `mf_rank` 这个名字，会把 runtime 综合排序语义与研究层的 moneyflow 因子语义混在一起，污染解释、研究和后续因子化改造。

## What Changes

- 将 runtime 对外正式语义从 `mf_rank` 提升为 `final_score_rank`，覆盖 candidate audit、debug plan、daily diagnostics 和聚合 counters。
- 保留旧的 `mf_rank*` 字段与配置作为兼容别名，避免打碎历史产物、旧脚本和旧配置。
- 明确 `mf_score` 的正式语义为 `final_score_value` 的兼容别名，并在 candidate audit 中补出 canonical 字段。
- 不改默认排序行为，不改 topk、tilt、gate 的实际执行逻辑，只做边界命名治理。

## Capabilities

### New Capabilities
- `runtime-final-score-rank-surface`: 定义 runtime 候选排序、daily diagnostics 和聚合 counters 的正式 `final_score_rank` 语义与兼容别名规则。

### Modified Capabilities
- `candidate-plan-boundary-contracts`: 候选计划合同需要明确 canonical rank 字段从 `mf_rank` 升为 `final_score_rank`，并规定旧字段只作兼容别名。

## Impact

- 受影响代码主要位于 `backend/core/portfolio`、`backend/core/stage_pipeline`、`backend/api/backtest_v2`、`tests`。
- 不改变 `baseline_V10.1` 的默认排序、仓位和执行时点。
- 会新增 canonical 诊断字段，并让聚合层优先消费 `final_score_rank*`，同时兼容读取旧 `mf_rank*`。
