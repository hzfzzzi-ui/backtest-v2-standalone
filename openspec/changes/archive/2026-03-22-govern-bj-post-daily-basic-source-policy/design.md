## Context

`BJ post-2021-11-15` 的 `turnover_rate_imputed_zero` 当前主要挂在 `fallback_available`。但最近的根因审计表明：

- 缺口样本全部 `source_daily_basic_present = false`；
- 绝大多数同时 `float_share/free_share = null`，无法走公式回填；
- `AkShareTurnoverCache` 对样本在缺口期返回 `(None, None)`；
- 头部 symbol 的 `raw_tushare_daily_basic` 首次出现日期显著滞后于北交所开市日期。

这说明该异常更接近“provider coverage gap”，而不是构建逻辑没有消费到本应存在的源。

## Goals

- 把 `BJ post` 的 `turnover_rate` 缺口从泛化 `fallback_available` 收敛成显式 `bj_post_daily_basic_gap`。
- 让 hard gate 只统计真实 critical 构建异常，不再把 `BJ post` 已知 provider gap 计入有效 `critical_exception_rows`。
- runtime 继续保守排除，但保留单独可见性。

## Non-Goals

- 不新增外部补源。
- 不把 `BJ post` 低置信 `turnover_rate` 放进 runtime 可消费层。
- 不尝试用未来 `float_share` 回填历史缺口。

## Decision

### 1. 统一 cause class

在 `_resolve_turnover_rate()` 中，当满足以下条件时，将 `BJ post` 的 imputed zero 收敛成 `bj_post_daily_basic_gap`：

- `market_phase = bj_post_20211115`
- `basic_turnover` 缺失
- `AkShare` fallback 为空
- 当前 `float_share` / 前值 `float_share` 都无法公式求解

这条规则适用于：

- `row_status = traded`
- `row_status = synthetic_gap_fill`
- 少量有 `stk_limit` 但仍无 `daily_basic` 的样本

### 2. 扩展 known source gap 键

在公共常量里将以下键加入 `KNOWN_SOURCE_GAP_ISSUE_CAUSES`：

- `("turnover_rate_imputed_zero", "bj_post_daily_basic_gap")`

这样 formal audit 的 canonical gate 可以直接复用上一步已经建立的 raw/effective critical 统计框架。

### 3. runtime 保持保守

runtime exclusion reason `known_source_gap_low_turnover` 扩展到 `BJ post` 的 traded 行，但只在以下条件下命中：

- `market_phase = bj_post_20211115`
- `turnover_rate_confidence < 1`
- `turnover_rate_source = imputed_zero`
- `source_daily_basic_present = false`
- `float_share` 与 `free_share` 均为空

`synthetic_gap_fill` 行仍然优先按 `row_status_synthetic_gap_fill` 排除。

### 4. 重刷受影响切片

为了让 formal audits 不再混入旧 cause class，需要重刷：

- `2021-11-15 ~ 2026-03-20`
- `market_phase = bj_post_20211115`
- `turnover_rate_source = imputed_zero`

之后重跑 `pams_ohlcv_daily_v2_formal_audits`。

## Risks

- 如果直接把 `BJ post` 全部 `turnover_rate_imputed_zero` 都改成已知源断层，而不约束 `source_daily_basic_present/float_share` 条件，可能会吞掉未来真正的构建回归。
- 如果 runtime 一并放宽，会把这批 provider gap 推进默认消费层，违反当前保守要求。

## Rollback

- 撤回 `bj_post_daily_basic_gap` cause class。
- 从 `KNOWN_SOURCE_GAP_ISSUE_CAUSES` 中删掉 `BJ post` 键。
- 恢复 runtime 对 `BJ post` 的统一 `low_turnover_rate_confidence` 统计。
- 重刷受影响 `BJ post` 切片并重跑 formal audits。
