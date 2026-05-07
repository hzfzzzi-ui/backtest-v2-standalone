## Why

当前主线配置里 `Risk Gate` 是正式信号组合模块，但它仍然以隐含规则、soft-weight 和 veto 条件散落在 runtime 中，尚未形成独立的研究对象。这会导致两个问题：

1. 无法回答 `Risk Gate` 本身到底在过滤什么、惩罚什么。
2. 无法区分主线收益到底来自原始 alpha，还是来自风险门控后的幸存样本。

现在需要先把主线里的 `Risk Gate` 正式拆成研究层 catalog、snapshot 和 study surface，但不改变任何 runtime 主行为。

## What Changes

- 新增 risk gate factor catalog，首版把主线里真实参与交易的风险门控上下文收成独立研究因子。
- 新增 risk gate factor snapshots 与 factor score snapshots，要求能把 gate/veto/soft-weight 相关信息按日写出。
- 新增 risk gate factor study surface，让 `Risk Gate` 可以像 stock alpha / state score / moneyflow 一样独立研究。
- 明确这条 change 仅属于研究层，不接入正式主线排序、预算或执行逻辑。

## Capabilities

### New Capabilities
- `risk-gate-factor-catalog`: 定义主线 Risk Gate 研究因子的正式目录与解释边界。
- `risk-gate-factor-snapshots`: 定义 Risk Gate 研究快照与组合分数快照。
- `risk-gate-factor-study-surface`: 定义 Risk Gate 单因子/组合因子研究入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies/factors`、`tests` 和 `openspec`。
- 不改变当前 `baseline_V10.1` runtime 排序、仓位、状态和退出行为。
- 后续如果要把 Risk Gate 因子重新接回 runtime，应作为单独 change 处理。
