## Context

最新 full-window audit 已经证明 formal window 口径问题解决了，但 canonical gate 仍被 `eligible_no_source` 阻塞。进一步拆样本后发现，`source_unresolved` 里的绝大多数 `SH/SZ` 行并不是“完全无源”，而是缺少 `daily` 与 `suspend_d`，但同日仍保留 `adj_factor`、`daily_basic` 或 `stk_limit` 等侧证据。当前实现把这两类问题都记成 `eligible_no_source`，等于把“低可信补位”误写成“完全无源”。

本次边界很窄：只修 `SH/SZ` 中的侧证据 gap fill 归类和 audit 统计，不触碰 `BJ`、security master 大边界、runtime 消费规则，也不把这类行伪装成 `suspended_confirmed`。

## Goals / Non-Goals

**Goals:**

- 在 canonical build 中识别 `SH/SZ` 的 side-evidence gap fill。
- 把这类行从 `source_unresolved` 中分流为 `synthetic_gap_fill`。
- 让 `eligible_no_source` 只代表真正无源的 unresolved。
- 保留 runtime 对 `synthetic_gap_fill` 的排除语义不变。

**Non-Goals:**

- 本次不修改 `BJ pre/post 2021-11-15` 的治理规则。
- 本次不把 side-evidence gap fill 升格为 `suspended_confirmed`。
- 本次不修改 `security_master` 边界或新增外部数据源。

## Decisions

### 1. `SH/SZ` 只要同日存在侧证据，就从 `source_unresolved` 提升为 `synthetic_gap_fill`

决策：

- 当且仅当满足以下条件时，将行状态记为 `synthetic_gap_fill`：
  - `market_phase in {'sh', 'sz'}`
  - `daily_present = false`
  - `suspend_present = false`
  - `source_adj_factor_present` 或 `source_daily_basic_present` 或 `source_stk_limit_present` 为真

原因：

- 这类行不能被叫做 `suspended_confirmed`，因为缺少停牌主证据。
- 但它们也不该继续叫 `source_unresolved`，因为“完全无源”并不属实。

备选方案：

- 直接升格为 `suspended_confirmed`：拒绝。证据等级不够。
- 保持 `source_unresolved` 不动：拒绝。会继续污染 `eligible_no_source`。

### 2. `eligible_no_source` 只统计真正无源行

决策：

- build 阶段只对 `source_unresolved` 增加 `eligible_no_source_rows` 和同名 exception。
- `synthetic_gap_fill` 记录独立 exception，例如 `synthetic_gap_fill_side_evidence`，便于审计但不再混入 `eligible_no_source`。

原因：

- `eligible_no_source` 这个标签本身就表示 “no source”。
- 如果继续把有侧证据的行塞进来，门禁信号会失真。

### 3. runtime 继续排除 `synthetic_gap_fill`

决策：

- 不改 runtime exclusion 语义，`synthetic_gap_fill` 仍作为非 runtime-eligible 记录保留。

原因：

- 当前任务只修 canonical 分类与 audit 语义，不推进 runtime 放开。
- 这样可以降低 canonical 误报，同时不改变 `baseline_V10.1` 的消费边界。

## Risks / Trade-offs

- [把侧证据 gap fill 从 `eligible_no_source` 中移出，可能让 canonical gate 数字大幅下降] -> 保留单独 exception 与 runtime 排除，避免被误解成“这些行已高可信”。
- [规则若误伤 `BJ` 或其他阶段，会把 mapping 问题洗掉] -> 本次实现明确限制在 `SH/SZ`。
- [头部簇多为历史长停牌，局部 symbol slice 重建后仍会残留无侧证据尾部] -> 这是预期行为，本次只清第一层。

## Migration Plan

1. 补 OpenSpec delta specs，固化侧证据 gap fill 与 `eligible_no_source` 的边界。
2. 修改 canonical build 和 audit 统计。
3. 增加单测覆盖 side-evidence 与 true-no-source 两种分支。
4. 先对头部 `SH/SZ` symbol 簇做 slice rebuild。
5. 重跑 full-window audit，记录 `eligible_no_source` 与 `source_unresolved` 的降幅及剩余阻塞。

## Open Questions

- `BJ post-2021-11-15` 中同样带侧证据的 unresolved，是否应沿用同一规则，留待下一轮处理。
