## Context

当前 `BJ pre-2021-11-15` 的 `turnover_rate` 异常已经被重新标成 `bj_pre_daily_basic_gap`，但 formal audit 仍然只按 `issue_type` 聚合 `critical_exception_rows`。因此：

- `2012-2017` 的 hard gate 仍把这 `26364` 行计成 critical；
- `2016-2026` 在 `2018-2021` 这段还残留旧的 `mapping_failure` 异常，因为受影响切片尚未按新 cause class 重刷；
- runtime gate 目前只知道“低 `turnover_rate_confidence`”，不知道其中哪些是已知源断层。

## Goals

- formal audit 必须把 `BJ pre daily_basic` 断层从“未知 critical”改成“显式已知源缺口”。
- summary 必须同时保留原始 critical 总量和剔除已知源缺口后的有效 critical 总量。
- runtime 继续保守排除这批样本，但要单独统计，不再和其他低置信 `turnover_rate` 混在一起。

## Non-Goals

- 不新增 `turnover_rate` 外部补源。
- 不提高 `BJ pre` 的 `turnover_rate_confidence`。
- 不把 `BJ pre` 低置信 `turnover_rate` 放进 runtime 可消费集合。

## Decision

### 1. 定义“已知源断层”键

在公共常量里增加显式键集合，第一批只包含：

- `("turnover_rate_imputed_zero", "bj_pre_daily_basic_gap")`

formal audit 和 runtime 可见性都基于这组键，而不是写散落的字符串判断。

### 2. canonical gate 输出 raw/effective 双口径

canonical gate 新增三个字段：

- `critical_exception_rows_raw`
- `known_source_gap_rows`
- `critical_exception_rows`

其中：

- `critical_exception_rows_raw`：沿用旧口径，统计全部 critical issue key。
- `known_source_gap_rows`：统计命中已知源断层键的 distinct `(trade_date, symbol, issue_type)`。
- `critical_exception_rows`：`raw - known_source_gap` 后的有效 hard gate 阻塞数。

`can_promote_shadow` 继续只看 `critical_exception_rows == 0`。

### 3. runtime gate 保持保守，但拆出已知源断层

runtime exclusion reason 增加：

- `known_source_gap_low_turnover`

只用于：

- `market_phase = bj_pre_20211115`
- `turnover_rate_confidence < 1`
- `turnover_rate_source = imputed_zero`

这批行仍然被排除，`can_consume_v10_1` 的判定不放宽。

### 4. 重刷受影响 BJ pre 切片

为了避免 `2016-2026` summary 继续混入旧 `mapping_failure`，需要按新逻辑重刷：

- `2016-03-01 ~ 2021-11-12`
- 受影响 `BJ pre turnover_rate_imputed_zero` symbol 集合

然后重跑 `pams_ohlcv_daily_v2_formal_audits`。

## Risks

- 如果只改 audit、不重刷切片，`2016-2026` 仍会混入旧 `mapping_failure`，结果不稳定。
- 如果 runtime 顺手放宽，会把“已知断层”误推进默认消费层，违反当前保守约束。

## Rollback

- 删除已知源断层键集合。
- 恢复 canonical gate 只输出单一 `critical_exception_rows`。
- 恢复 runtime 的统一 `low_turnover_rate_confidence` 口径。
- 重新重刷受影响 `BJ pre` 切片并重跑 formal audits。
