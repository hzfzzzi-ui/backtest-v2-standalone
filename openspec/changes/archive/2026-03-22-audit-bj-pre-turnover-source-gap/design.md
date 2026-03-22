## Context

在 `V2` 当前实现里，`_resolve_turnover_rate()` 对 `bj_pre_20211115` 的失败分支会直接标记 `mapping_failure`。但实库和样本核查显示：

- 这些行往往 `row_status = traded`
- 原始日线存在
- `raw_tushare_daily_basic` 在该阶段长期缺失
- AkShare fallback 也经常返回空结果

所以这类异常更准确的语义是“BJ pre 的 daily_basic 源缺口”，而不是“symbol mapping 失败”。

## Goals / Non-Goals

**Goals**

- 提高 `bj_pre` turnover 异常的审计真相度
- 让后续治理直接看到“源缺口”而不是被 `mapping_failure` 误导

**Non-Goals**

- 不修改 turnover_rate 数值
- 不修改 confidence 规则
- 不在本次变更中引入新的外部数据源

## Decision

将 `bj_pre_20211115` 的 fallback cause class 改成 `bj_pre_daily_basic_gap`，并把 `basic_turnover` 写入 `issue_detail`。

这是一个审计语义修正，不会改变：

- `turnover_rate = 0`
- `turnover_rate_source = imputed_zero`
- `turnover_rate_confidence = 0`

## Risks

- 历史 exception 的旧 cause class 不会自动改名，必须通过受影响切片重建刷新。
- 这次变更不能降低 `critical_exception_rows`，只能让后续治理方向更准确。

## Rollback

- 将 cause class 改回 `mapping_failure`
- 移除 `basic_turnover` 诊断字段
- 重刷受影响 BJ 切片
