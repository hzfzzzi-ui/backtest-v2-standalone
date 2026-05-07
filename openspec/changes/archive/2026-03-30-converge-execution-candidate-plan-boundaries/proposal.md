## Why

上一条变更已经把子系统候选边界从执行内核前移为 `candidate_boundary_v1`，并确认 `baseline_V10.1` 无漂移。但当前 `order_planning` 仍直接消费 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*` 等上游候选规划兼容逻辑，执行内核和个股子系统的候选规划语义仍未完全分层。

现在需要继续收敛这条边界，把“候选规划/轮换替换/现金感知搜索”从执行内核侧抽离成独立正式合同，避免执行内核继续感知股票侧兼容策略细节。

## What Changes

- 新增上游候选规划正式合同，定义 `candidate_plan_v1`，用于表达候选边界确认后的最终候选计划、替换动作和规划摘要。
- 修改执行内核边界，使 `order_planning` 不再直接读取 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*` 等候选规划兼容配置，只消费 `candidate_plan_v1` 与执行级 sizing 必需参数。
- 明确个股子系统负责形成候选规划真相，执行内核只负责把已确认的候选计划变成订单和目标持仓。
- 同步正式审计与架构文档，使候选边界层、候选规划层和执行内核层的分工可审计、可追踪。

## Capabilities

### New Capabilities
- `candidate-plan-boundary-contracts`: 定义候选规划层的正式合同、最小 payload 和与执行内核的交接边界。

### Modified Capabilities
- `runtime-boundary-contracts`: 执行内核输入边界从“候选边界 + 兼容配置”收敛为“候选边界 + 候选规划合同 + 统一目标持仓”。
- `cn-stock-trend-alpha-core`: 个股子系统需要在进入执行内核前完成轮换替换、现金感知候选选择等候选规划语义。
- `backtest-research-audit`: 审计需要区分候选边界层、候选规划层和执行内核层的拒绝与归因。
- `architecture-doc`: 系统架构图和阶段流水线边界需要补入候选规划层的正式位置。

## Impact

- 影响代码主要集中在 `backend/core/stage_pipeline/adapters/order_planning.py`、候选边界相关适配器、个股候选规划相关调用链、正式审计产物和文档。
- 不改变 `baseline_V10.1` 的正式研究口径，不引入新的资产池、市场状态或风险预算逻辑。
- 会新增一个正式运行时合同，并要求相关测试与基线回归继续验证无漂移。
