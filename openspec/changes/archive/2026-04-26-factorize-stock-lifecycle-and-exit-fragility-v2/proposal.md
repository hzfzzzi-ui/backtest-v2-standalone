## Why

当前个股主线的大部分 rank 因子已经拆开，但研究结果反复说明：主线收益更像来自持有期赢家、生命周期管理和退出规则，而不是简单横截面排序。第一版 `breakout failure / exit fragility` 只抓到了当日 breakout 上下文，没有真正覆盖“持有后为什么变脆、为什么被错误地继续持有、为什么最终被退出”这条主线收益链条，因此现在需要做第二版拆分。

## What Changes

- 新增个股生命周期 fragility 研究目录，把 entry 后的早期衰减、弱 carry、破位风险、退出前脆弱性等对象正式收成研究因子。
- 新增生命周期 fragility snapshots 与组合分数快照，要求按主线锚定窗口可审计输出。
- 新增生命周期 / 退出风险 study surface，用于研究：
  - 哪类 entry 更容易在持有 early stage 演化成坏仓
  - 哪类持有上下文更容易触发 `pre_profit_breakout_failure`、`low10_exit`、`risk_off_exit`
  - 哪类退出是在剔除坏仓，哪类退出更像误杀
- 明确本轮只建设 `RESEARCH_ONLY` 合同，不改正式主线 runtime 行为。

## Capabilities

### New Capabilities
- `stock-lifecycle-fragility-catalog`: 定义个股生命周期 fragility 与退出风险研究因子的正式目录和解释边界。
- `stock-lifecycle-fragility-snapshots`: 定义生命周期 fragility 快照、组合分数快照与审计输出合同。
- `stock-lifecycle-fragility-study-surface`: 提供生命周期 / 退出风险三窗口研究入口与基础分析输出。

### Modified Capabilities
- None.

## Impact

- 影响代码：`backend/research`、`research/studies/factors`、`tests`、`openspec`。
- 影响系统：仅研究层，不修改 `baseline_V10.1` 默认排序、持仓、状态或退出行为。
- 影响产物：新增生命周期 fragility factor snapshot、study output 和三窗口主线锚定研究定义。
