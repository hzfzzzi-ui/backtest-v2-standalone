## MODIFIED Requirements

### Requirement: `v2` 构建 MUST 输出逐日审计与异常明细
系统 MUST 为 `pams_ohlcv_daily_v2` 输出逐日审计表 `pams_ohlcv_daily_v2_audit_daily` 和异常明细表 `pams_ohlcv_daily_v2_exceptions`，以覆盖行集、字段、侧表和源异常。`eligible_no_source` 与 `eligible_missing_daily_count` MUST 只反映真正无源的 `source_unresolved`；带有 side evidence 的 `synthetic_gap_fill` MUST 以独立异常类型审计，而 SHALL NOT 混入 `eligible_no_source`。

#### Scenario: 逐日审计输出主表与侧表覆盖
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为窗口内每个 `trade_date` 输出 `eligible_symbol_count, raw_daily_count, v2_count, daily_basic_join_count, moneyflow_join_count, eligible_missing_daily_count, daily_basic_missing_count, moneyflow_missing_count`

#### Scenario: 真无源 unresolved 计入 eligible no source
- **WHEN** 某日存在 `row_status='source_unresolved'` 且缺少 `daily`、`suspend_d` 与允许的 side evidence
- **THEN** 该日 `eligible_missing_daily_count` MUST 包含这些行
- **THEN** 系统 MUST 记录 `eligible_no_source` 异常

#### Scenario: 侧证据 synthetic gap fill 不计入 eligible no source
- **WHEN** 某日存在 `row_status='synthetic_gap_fill'` 且该行保留了 side evidence
- **THEN** 该行 SHALL NOT 被计入 `eligible_missing_daily_count`
- **THEN** 系统 MUST 记录独立的 synthetic gap fill 异常，以便继续审计
