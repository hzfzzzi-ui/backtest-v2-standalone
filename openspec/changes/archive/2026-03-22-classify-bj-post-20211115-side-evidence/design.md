## Context

`SH/SZ` side-evidence unresolved 已经清完，最新数据库查询显示剩余 `bj_post_20211115` unresolved 约 `36657` 行，其中约 `36654` 行同日保留了 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据。这说明 `BJ post-2021-11-15` 的主问题形态与此前 `SH/SZ` 已治理的问题相同：缺主证据，但并非完全无源。

与之相对，`bj_pre_20211115` 仍主要表现为映射与口径问题，当前系统已通过 `mapping_failure` 和 `skipped_bj_pre_no_evidence_rows` 对其单独治理。本次不能把这两类问题混在一起。

## Goals / Non-Goals

**Goals**

- 把 `bj_post_20211115` 中带同日侧证据的 unresolved 从 `source_unresolved` 分流为 `synthetic_gap_fill`。
- 保持 `eligible_no_source` 只表示真无源 unresolved。
- 保持 runtime 对 `synthetic_gap_fill` 的排除语义不变。
- 通过局部 slice rebuild 和 full-window audit 验证指标下降是否来自分类修正而非口径放松。

**Non-Goals**

- 不修改 `bj_pre_20211115` 的治理规则。
- 不把 `BJ post-2021-11-15` 的 side-evidence gap fill 升格为 `suspended_confirmed`。
- 不新增外部数据源，也不改 `security_master` 边界。
- 不放宽 runtime gate 或 baseline 默认消费口径。

## Decisions

### 1. `bj_post_20211115` 复用既有 side-evidence gap fill 规则

决策：

- 当且仅当满足以下条件时，把行状态记为 `synthetic_gap_fill`：
  - `market_phase == 'bj_post_20211115'`
  - `daily_present = false`
  - `suspend_present = false`
  - 同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据

原因：

- 这类行不能被写成 `suspended_confirmed`，因为仍缺停牌主证据。
- 但继续写成 `source_unresolved` 也不准确，因为它们并非完全无源。

### 2. `bj_pre_20211115` 明确排除在本次扩展之外

决策：

- 分类器只扩展到 `bj_post_20211115`，不修改 `bj_pre_20211115` 的任何分支。

原因：

- `bj_pre_20211115` 现有问题主要是映射缺口，不是本次要解决的 side-evidence 归类问题。
- 如果把 `bj_pre_20211115` 也并入，会把 mapping failure 洗进 `synthetic_gap_fill`，破坏异常分层。

### 3. Audit 语义保持不变，只扩大 `synthetic_gap_fill` 的适用范围

决策：

- `eligible_missing_daily_count` 与 `eligible_no_source` 继续只统计 `source_unresolved`。
- `synthetic_gap_fill_side_evidence` exception 继续独立记录，包括这次新增的 `BJ post-2021-11-15` 行。

原因：

- 这样可以继续压低 canonical 误报，同时不改变 runtime exclusion。

## Risks / Trade-offs

- 如果误把 `bj_pre_20211115` 纳入，会把 mapping 问题洗成 side-evidence gap fill。
- 如果只看分类下降、不看 runtime 变化，容易误判为“数据已经正式可消费”。
- `BJ post-2021-11-15` slice rebuild 规模较大，应该先从头部 symbol 批次开始，再跑 full-window audit。

## Migration Plan

1. 补齐 OpenSpec proposal/design/specs/tasks，明确 `bj_post_20211115` 与 `bj_pre_20211115` 的边界。
2. 修改分类器，把 `bj_post_20211115` 纳入 side-evidence gap fill 范围。
3. 增加 `BJ post-2021-11-15` 回归测试，并补一个 `bj_pre_20211115` 非回归测试。
4. 先对头部 `BJ` symbol 做 slice rebuild。
5. 重跑 full-window audit，记录 `eligible_no_source`、`critical_exception_rows`、`synthetic_gap_fill_rows` 与 runtime 指标变化。
