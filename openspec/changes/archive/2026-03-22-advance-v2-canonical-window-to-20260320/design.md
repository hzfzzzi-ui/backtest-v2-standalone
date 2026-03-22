## Context

当前数据库事实已经变化：`v2` 主表、moneyflow 和 whitelist 都已追到 `2026-03-20`。但 formal gate 的“窗口是否完整”仍由 `OFFICIAL_END_DATE = 2026-03-16` 驱动，导致同一份数据库在运行层被视为已补齐，在审计层却仍被视为未完成 full-window。

这类漂移不属于一般文档瑕疵，而是正式口径错误：它会污染 backfill 默认行为、AkShare fallback 截止日期、audit gate 判定以及 runbook 操作命令。当前任务的边界是修正这条单一真相链，并重跑 audit 验证真实阻塞项；不把 unresolved 数据问题和口径修复混成一次“大清洗”。

## Goals / Non-Goals

**Goals:**

- 将 `v2` 正式窗口终点统一为 `2026-03-20`。
- 让 full-window audit 只依赖单一 official window 定义，不再散落硬编码。
- 补充最小测试，覆盖新的 official window 和 full-window gate 语义。
- 用 `2007-01-04 ~ 2026-03-20` 的 full audit 给出最新 canonical gate 结论。

**Non-Goals:**

- 本次不修改 `baseline` 主逻辑、benchmark、regime 或 runtime 消费口径。
- 本次不承诺消灭所有 `eligible_no_source`、`source_unresolved`、`turnover_rate_imputed_zero`。
- 本次不做新的数据源接入，也不修改 `sz300114` 之类具体缺口的治理规则。

## Decisions

### 1. 继续使用 `OFFICIAL_END_DATE`，但把它恢复成真正的单一真相源

决策：

- 保留 `pams_ohlcv_daily_v2_common.OFFICIAL_END_DATE` 作为正式窗口终点常量。
- 所有正式入口默认值和判定逻辑都引用这个常量，不再复制日期字符串。

原因：

- 当前主要问题不是没有统一入口，而是已有入口被陈旧常量污染。
- 最小改动就是把官方终点统一回一个常量，并清掉外围硬编码。

备选方案：

- 每个脚本单独改默认终点：拒绝。后续仍会再次漂移。
- 改成从数据库动态读取最新日期：拒绝。formal window 是治理口径，不是“当前数据库最大日期”。

### 2. canonical gate 必须显式暴露 official window 边界

决策：

- 在 audit 总结中输出 `official_window.start/end`。
- `has_full_window` 继续表示“本次审计窗口是否等于正式窗口”，但必须能被产物直接解释。

原因：

- 之前 summary 只有布尔值，没有把它依赖的正式窗口写出来，难以及时发现 stale constant。
- 对正式口径来说，可解释性和可审计性比简洁更重要。

备选方案：

- 只改布尔判定，不补 summary 字段：拒绝。用户仍需读源码才能知道 gate 在按哪个窗口判定。

### 3. 文档只同步正式操作入口，不追全仓历史日期文本

决策：

- 优先更新 `v2` runbook 和直接相关的 side-table runbook。
- 不在本次清理所有历史实验文档中出现的 `2026-03-16`。

原因：

- 用户当前要推进的是 V2 数据库主线，不是回写所有历史研究产物。
- 扩大到所有历史设计文档会明显超出最小改动边界。

## Risks / Trade-offs

- [formal window 提升后，更多脚本会默认跑到 `2026-03-20`] -> 通过单测和 runbook 明确默认值变化，避免误以为仍是 `2026-03-16`。
- [重跑 full audit 可能暴露更多真实阻塞项] -> 这是预期行为；本次不会把“gate 仍失败”误报成回归。
- [仍有未同步的历史文档保留 `2026-03-16`] -> 限定本次只同步正式入口和当前主线文档，避免过度扩散。

## Migration Plan

1. 更新 OpenSpec change 和 delta specs，固化正式窗口终点与 gate 语义。
2. 修改 `v2` 共用常量、full backfill 默认值、audit summary 输出和相关测试。
3. 更新当前主线 runbook 示例命令。
4. 重跑 `2007-01-04 ~ 2026-03-20` full-window audit。
5. 若审计仍失败，保留失败事实并单独列出真实 unresolved 阻塞项；不回退 window 口径。

## Open Questions

- `sz300114` 这类长期 unresolved 是 security master 边界问题、Tushare源缺口，还是 symbol lineage 治理问题，需要下一轮单独定界。
