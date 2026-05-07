## Why

当前主线真实排序核心仍然是 `final_score`，但它的组成项还散落在 breakout provider precompute 与 day signal meta 中，没有形成独立的研究对象。这会导致两个问题：

1. 无法回答主线收益到底来自哪些 `final_score` 组成项。
2. 无法区分综合排序结果和原子上下文因子的真实贡献。

现在需要先把主线里的 `final_score` 组成正式拆成研究层 catalog、snapshot 和 study surface，但不改变任何 runtime 主行为。

## What Changes

- 新增 final score composition catalog，首版把主线真实参与 `_final_score` 合成的核心组成项收成独立研究因子。
- 新增 final score composition snapshots 与 factor score snapshots，要求能把组成项与总分按日写出。
- 新增 final score composition study surface，让 `final_score` 的组成可以像 stock alpha / risk gate / moneyflow 一样独立研究。
- 明确这条 change 仅属于研究层，不接入正式主线排序、预算或执行逻辑。

## Capabilities

### New Capabilities
- `final-score-composition-catalog`: 定义主线 `final_score` 组成研究因子的正式目录与解释边界。
- `final-score-composition-snapshots`: 定义 `final_score` 组成研究快照与组合分数快照。
- `final-score-composition-study-surface`: 定义 `final_score` 组成单因子/组合因子研究入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies/factors`、`tests` 和 `openspec`。
- 不改变当前 `baseline_V10.1` runtime 排序、仓位、状态和退出行为。
- 后续如果要把某个组成项重新接回 runtime，应作为单独 change 处理。
