## Why

当前主线真实收益很大一部分来自持有期管理和退出规则，但 `pre_profit_breakout_failure`、`low10_exit`、`risk_off_exit` 等失败/脆弱性逻辑仍然散落在 runtime 中，没有形成独立的研究对象。这会导致两个问题：

1. 无法回答哪些 entry context 更容易演化成 breakout failure。
2. 无法区分主线收益到底来自 entry alpha，还是来自对脆弱仓位的及时剔除。

现在需要先把主线里的 breakout failure / exit fragility 正式拆成研究层 catalog、snapshot 和 study surface，但不改变任何 runtime 主行为。

## What Changes

- 新增 breakout failure / exit fragility factor catalog，首版把与失败风险和脆弱退出最相关的上下文收成独立研究因子。
- 新增 breakout failure / exit fragility snapshots 与 factor score snapshots，要求能把 failure-risk/fragility 相关信息按日写出。
- 新增 breakout failure / exit fragility study surface，让这类失败风险可以像 stock alpha / risk gate / final score 一样独立研究。
- 明确这条 change 仅属于研究层，不接入正式主线排序、预算或执行逻辑。

## Capabilities

### New Capabilities
- `breakout-failure-fragility-catalog`: 定义主线 breakout failure / exit fragility 研究因子的正式目录与解释边界。
- `breakout-failure-fragility-snapshots`: 定义 breakout failure / exit fragility 研究快照与组合分数快照。
- `breakout-failure-fragility-study-surface`: 定义 breakout failure / exit fragility 单因子/组合因子研究入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies/factors`、`tests` 和 `openspec`。
- 不改变当前 `baseline_V10.1` runtime 排序、仓位、状态和退出行为。
- 后续如果要把 failure/fragility 因子重新接回 runtime，应作为单独 change 处理。
