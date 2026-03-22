## MODIFIED Requirements

### Requirement: `v2` 构建 MUST 输出逐日审计与异常明细
系统 MUST 为 `pams_ohlcv_daily_v2` 输出逐日审计表 `pams_ohlcv_daily_v2_audit_daily` 和异常明细表 `pams_ohlcv_daily_v2_exceptions`，以覆盖行集、字段、侧表和源异常。`eligible_no_source` 与 `eligible_missing_daily_count` MUST 只反映真无源的 `source_unresolved`；对 `SH/SZ` 与 `BJ post-2021-11-15` 中带同日 side evidence 的 `synthetic_gap_fill`，系统 MUST 以独立异常类型审计，而 SHALL NOT 混入 `eligible_no_source`。`bj_pre_20211115` 的 mapping 类问题 SHALL NOT 因本规则被并入 `synthetic_gap_fill` 审计。

#### Scenario: 真无源 unresolved 计入 eligible no source
- **WHEN** 某日存在 `row_status='source_unresolved'` 且缺少 `daily`、`suspend_d` 与允许的 side evidence
- **THEN** 该日 `eligible_missing_daily_count` MUST 包含这些行
- **THEN** 系统 MUST 记录 `eligible_no_source` 异常

#### Scenario: BJ post-2021-11-15 side-evidence synthetic gap fill 不计入 eligible no source
- **WHEN** 某日存在 `row_status='synthetic_gap_fill'`，且该行属于 `BJ post-2021-11-15` 并保留了 side evidence
- **THEN** 该行 SHALL NOT 被计入 `eligible_missing_daily_count`
- **THEN** 系统 MUST 记录独立的 synthetic gap fill 异常

#### Scenario: BJ pre-2021-11-15 映射问题不并入 synthetic gap fill
- **WHEN** 某日存在 `bj_pre_20211115` 的 unresolved 行
- **THEN** 系统 SHALL NOT 仅因本规则把它从 `eligible_no_source` 或 mapping 相关异常改记为 `synthetic_gap_fill`
