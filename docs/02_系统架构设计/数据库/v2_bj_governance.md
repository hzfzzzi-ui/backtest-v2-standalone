# `BJ` 治理说明

## 1. 正式结论

`BJ` 是 `V2` 正式治理范围的一部分，不能通过排除 `BJ` 来让 `V2` 通过门禁。

但 `BJ` 必须拆成两个阶段治理：
- `BJ pre-2021-11-15`
- `BJ post-2021-11-15`

## 2. 为什么要拆

北交所于 `2021-11-15` 正式开市。当前 `v2` 审计显示，`bj%` 异常的大头发生在这一天之前，因此不能把全部 `bj%` 缺失都解释为“正式北交所阶段拿不到数据”。

当前专项审计产物：
- [BJ 前后专项审计报告](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v2_bj_pre_post_20211115_audit_20260318/report.md)
- [BJ 前后专项审计摘要](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/v2_bj_pre_post_20211115_audit_20260318/summary.json)

## 3. 阶段定义

### 3.1 `BJ pre-2021-11-15`

治理目标：
- 识别历史映射、平移和 lineage 污染
- 判断这些记录在 canonical 中应如何表达

主要问题类型：
- `mapping_failure`
- `missing_in_all_sources`
- `source_present_low_confidence_fill`

### 3.2 `BJ post-2021-11-15`

治理目标：
- 识别正式北交所开市后的真实源覆盖问题
- 判断哪些字段可由 `AkShare`、`巨潮资讯` 等补源修复

主要问题类型：
- `missing_in_all_sources`
- `fallback_available`
- 少量 `build_rule_rejected`

## 4. 当前治理纪律

- `BJ` 不能从正式数据库目标中删除
- `BJ pre-2021-11-15` 不能直接按“正式北交所缺数”解释
- `BJ post-2021-11-15` 应单独做 source coverage 审计
- 所有 `BJ` 结论必须引用 `2021-11-15` 分段结果
