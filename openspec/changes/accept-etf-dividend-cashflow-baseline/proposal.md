## Why

2026-05-08 在容器内重跑 `baseline_V10.1` 时，候选实验 `exp_20260508_124555553_fabd` 与正式锚点 `exp_20260426_005716047_8650` 出现可解释漂移：股票层完全一致，漂移来自 ETF 分红现金事件进入数据包后改变 ETF 现金流与 NAV 口径。

该漂移不是随机执行失败，而是 `pit_cn_etf_dividend_events` 补齐历史分红事件后，系统从隐含复权估值转向显式分红应收/到账记账。用户已明确接受新口径，因此需要把该口径登记为正式 baseline 口径，并保留旧锚点用于 replay 和审计。

## What Changes

- **BREAKING**: 当前正式 baseline 将从旧的 `CN_STOCK_ETF_FORMAL_V1` 锚点切换到包含 ETF 显式分红现金事件的新候选实验。
- ETF baseline 口径正式接受 `execution.dividend_cash_timing_mode = "pay_date"` 下的应收创建、到账结转和现金/NAV 闭环。
- 旧 baseline `exp_20260426_005716047_8650` 不再作为 live compare truth，降级为 replay/audit anchor。
- 新 baseline 必须记录本次口径差异来源：ETF 分红事件数据包从 4 行扩展到 37 行，首个 NAV 分歧发生在 `2015-01-20` 的 `sh510300` 分红事件。
- 重锚后必须重新执行容器内 baseline regression，确认新 baseline 对自身回归通过。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `etf-dividend-cash-events`: 将 ETF 显式分红现金事件从已实现能力提升为当前正式 stock+ETF baseline 的口径要求。
- `baseline-anchor-registration`: 允许在人工确认后把含 ETF 分红现金流的新候选实验注册为 active baseline，并要求旧 baseline 显式降级保留。

## Impact

- 影响 `outputs/baselines/` 中的正式 baseline 注册记录、索引和相关快照。
- 影响 baseline regression 的 compare truth。
- 影响研究解释：ETF sleeve 的 NAV、现金、交易股数和组合层指标会因显式分红现金事件发生小幅漂移。
- 不改变股票层信号、成交时点、排序主因子、资产池或组合构建逻辑。
- 不修改前端展示层和 API 主输出结构；展示层应继续从 baseline truth 读取结果。
