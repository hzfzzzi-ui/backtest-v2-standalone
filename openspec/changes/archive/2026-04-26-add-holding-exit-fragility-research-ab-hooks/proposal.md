## Why

当前 `pre_profit_failure_context_risk` 的研究已经说明，它更像“持仓后、利润尚未建立前的失败风险”，而不是买入前候选风险。前一轮把它接到 candidate-layer veto 后，overlay 虽然启用，但对候选零匹配、零作用面，证明插入层级错误。现在需要把这条因子改为 holding/exit layer 的 `RESEARCH_ONLY` 插入点，避免继续在错误层级消耗研究预算。

## What Changes

- 新增持仓层 / 退出层的 research-only fragility hook，用于在已持仓股票上消费 `pre_profit_failure_context_risk` 这类生命周期风险因子
- 新增 research-only 审计产物，明确记录 fragility hook 的启用天数、覆盖持仓数、命中的风险桶与触发后的持仓结果差异
- 新增最小 holding/exit A/B 入口，只允许在 stock-only 基线下比较“基线”与“fragility hook”差异，不改默认主线行为
- 明确禁止将 lifecycle fragility 因子继续作为 candidate-layer veto / tiebreak 接入

## Capabilities

### New Capabilities
- `holding-exit-fragility-hooks`: 为 research-only runtime 提供持仓层 / 退出层 fragility 因子插入点与行为边界
- `holding-exit-fragility-audit`: 为 holding/exit fragility 实验提供可审计的日级与持仓级诊断输出
- `holding-exit-fragility-ab-surface`: 为 stock-only 基线提供最小 holding/exit fragility A/B 运行入口

### Modified Capabilities
- None.

## Impact

- 影响代码：`backend/core/portfolio`、`backend/core/stage_pipeline`、`backend/research`、`tests`、`openspec`
- 影响系统：仅限个股主线的 research-only A/B 插入点，不修改正式主线默认排序、候选过滤或退出逻辑
- 影响产物：新增 holding/exit fragility 研究诊断与 A/B 结果产物，继续沿用三窗口与当前 stock-only 基线锚点
