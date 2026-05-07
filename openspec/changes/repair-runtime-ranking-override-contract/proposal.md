## Why

当前 `baseline_V10_1` 的 live-like A 股主线路径在 legacy backend `runtime_config` 中仍保留了 `ranking_mode = residual_only` 与 `enable_residual_ranking = true`，但这类兼容输入在进入正式 `RuntimePlan.execution_overrides` 时没有被一次性收口。结果是候选计划层从未真正进入 `final_score / mf_rank` 排序分支，导致 live baseline 排序链成为死路径，现有 `B0 / A1_NO_RESIDUAL_RANK` 对照也无法回答残差排序是否有真实贡献。

这个缺口已经影响正式 runtime 行为解释与后续 baseline ablation 结论可信度，必须先以最小合同修复把“排序意图 -> 执行覆盖参数”接通，再继续讨论因子效果。

## What Changes

- 修订 runtime 边界合同：排序执行真相只允许存在于 `RuntimePlan.execution_overrides` / `execution_contract`，legacy `runtime_config.strategy.params` 只能作为兼容输入，不得与执行真相并列生效。
- 为直接消费 backend runtime config 的运行路径补齐一次性规范化步骤，在构建 `RuntimePlan` 时把 legacy 排序字段收口为正式 `execution_overrides`，保证 path-backed run、study run 与编译入口在排序语义上保持一致。
- 增加定向合同测试，覆盖 `residual_only`、`enable_residual_ranking=true` 与显式关闭排序三类情况。
- 仅重跑 `v10/live_baseline_ablation_s1` 的 `B0` 与 `A1_NO_RESIDUAL_RANK`，验证修复后排序链计数器不再全为 `0`，且两组结果产生可解释差异。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `runtime-boundary-contracts`: 运行时边界合同需要要求排序执行真相唯一收口到 `execution_overrides`，legacy `runtime_config.strategy.params` 只能作为规范化输入。

## Impact

- 影响代码：
  - `backend/core/engine_runtime/foundation_shell.py`
  - `backend/core/services/experiment_runtime_service.py`
  - 可能补充一个共享 helper，避免复制 compile path 的排序桥接逻辑
  - 相关单元测试与 `v10/live_baseline_ablation_s1` 复跑产物
- 不影响项：
  - 不修改 `baseline_V10_1` 配置文件
  - 不修改因子定义、market gate 规则、candidate plan 排序实现
  - 不新增新的排序模式
- 风险：
  - 这是 L3 runtime 行为修复，可能让当前 live-like A 股主线路径首次真正启用排序分支，回测结果会变化
  - 需要通过最小复跑把变化严格限定在 `B0 / A1` 对照组上验证
