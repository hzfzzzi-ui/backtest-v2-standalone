## Context

`BJ pre/post turnover_rate` 已经从 hard gate 的有效阻塞里拆出去后，`pre_close_imputed_zero` 成为下一条需要治理的线。根因审计表明：

- `2016-2026` 剩余的 9 行 `pre_close_imputed_zero` 都是 stale exception，主表当前已经是 `prev_close_carry`，异常表 `build_run_id` 仍停在旧 run。
- 当前有效的 `pre_close_imputed_zero` 样本几乎都从 symbol 在 `v2` 里的第一行开始连续出现，且在第一次 `daily` 出现后立即恢复正锚点。
- `2012-2017` hard gate 只剩 `sz000156 / sz000622 / sz000805` 三个 symbol，共 756 行，全部符合“起始连续左截断、无历史正锚点、后续首次 daily 到来后恢复”的结构。

这说明 `pre_close` 的问题不是普遍的构建回归，而是“stale audit 残留 + 历史左截断锚点缺口”混在一起。

## Goals / Non-Goals

**Goals:**

- formal audit 只统计当前主表仍然有效的异常，不再把 stale exception 混进 gate。
- 给左截断 `pre_close_imputed_zero` 一个显式可审计的 cause class。
- 让 canonical gate 将这类已知源边界记入 `known_source_gap_rows`，而不是继续算作有效 critical。
- 保持 runtime 保守，不放宽低可信 `pre_close` 的默认消费。

**Non-Goals:**

- 不用未来出现的 `daily` 或 `close` 去反向回填历史 `pre_close`。
- 不补新的外部历史源。
- 不顺手处理配对的 `turnover_rate_imputed_zero`，那条线留到下一刀单独推进。
- 不修改 `v2` 主表的 runtime 过滤门槛。

## Decisions

### 1. formal audit 以“当前主表仍生效的异常”为准

`critical_exception_rows`、异常 breakdown 和 key drilldown 全部改为只统计与当前主表同一 `build_run_id` 的 symbol 级异常。这样可以清掉已经被后续重建修复、但旧异常明细尚未删除的残留记录。

不选择“先手工删库再继续”，因为 stale exception 是审计口径问题，不应依赖一次性清库修复。

### 2. `pre_close_imputed_zero` 只在非 traded 的左截断样本上收敛成 `left_censored_anchor_gap`

当行状态属于 `synthetic_gap_fill / suspended_confirmed / delist_tail_confirmed`，且系统在当前行仍无法从 `daily_pre_close / prev_close_carry / basic_close_anchor / daily_close_anchor` 得到正锚点时，将该异常收敛成 `left_censored_anchor_gap`。

不把 `source_unresolved` 也并入这条规则，因为真无源样本仍然需要继续保留为 unresolved 主问题。

### 3. runtime 保持不放宽

这次只修 canonical hard gate 的解释边界。runtime 仍继续按低可信 `pre_close` 排除，不新增默认消费。

不选择同步放开 runtime，因为左截断已知源缺口仍然没有真实价格锚点，直接消费会把审计修正误当成数据补齐。

## Risks / Trade-offs

- [风险] `left_censored_anchor_gap` 条件写得过宽，会吞掉真实的中段构建回归。
  - 缓解：只允许非 `traded` 行命中，并用单测锁住 `source_unresolved` 不并入这条规则。
- [风险] audit 改成只看当前 `build_run_id` 后，旧 exception 明细仍留在库里，可能让人工直查时困惑。
  - 缓解：在 runbook 中明确 formal audit 只统计 current exception，并保留 stale 查询命令。
- [风险] `2012-2017` hard gate 即使清掉 `pre_close`，仍会剩下配套的 `turnover_rate_imputed_zero`。
  - 缓解：把这次 change 收窄到 `pre_close`，完成后再单独起下一刀处理 paired turnover。
