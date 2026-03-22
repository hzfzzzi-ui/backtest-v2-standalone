# cn-stock-v2-audit-gates Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: `v2` 构建 MUST 输出逐日审计与异常明细
系统 MUST 为 `pams_ohlcv_daily_v2` 输出逐日审计表 `pams_ohlcv_daily_v2_audit_daily` 和异常明细表 `pams_ohlcv_daily_v2_exceptions`，以覆盖行集、字段、侧表和源异常。

#### Scenario: 逐日审计输出主表与侧表覆盖
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为窗口内每个 `trade_date` 输出 `eligible_symbol_count, raw_daily_count, v2_count, daily_basic_join_count, moneyflow_join_count, eligible_missing_daily_count, daily_basic_missing_count, moneyflow_missing_count`

#### Scenario: 异常明细记录问题类型与样本
- **WHEN** 构建过程中出现 `eligible_no_source`、`raw_only_not_in_master`、`adj_factor_missing`、`daily_basic_missing`、`moneyflow_missing` 或软字段缺失
- **THEN** 系统 MUST 在异常表中记录 `trade_date, symbol, ts_code, issue_type, issue_detail, source_table, build_run_id`

### Requirement: `v2` MUST 输出 `v1/v2` 差异审计
系统 MUST 产出 `pams_ohlcv_daily` 与 `pams_ohlcv_daily_v2` 的逐日行数差异、关键字段空值差异和样本差异，以区分“覆盖修复”与“构建错误”。

#### Scenario: 逐日比较 v1 与 v2 行数
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为每个 `trade_date` 输出 `v1_count, v2_count, v2_minus_v1`

#### Scenario: 关键字段差异样本可追溯
- **WHEN** `v1` 与 `v2` 在某日存在显著行数或字段差异
- **THEN** 系统 MUST 输出至少一份样本明细以说明差异来自覆盖修复还是构建异常

### Requirement: `v2` 升格 MUST 通过数据库补全门禁
系统 MUST 仅在全历史回填完成、主表零行缺口成立、硬字段零空值成立且审计通过时，才允许将 `pams_ohlcv_daily_v2` 升格为正式 shadow 数据源。

#### Scenario: `eligible_no_source` 非零时禁止升格
- **WHEN** 全历史构建结果中仍存在任意 `eligible_no_source`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 硬字段仍有空值时禁止升格
- **WHEN** 全历史构建结果中任一硬字段仍存在空值
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 三窗口审计未完成时禁止升格
- **WHEN** `2016-2026`、`2007-2017`、`2007-2026` 任一窗口缺少正式审计结果
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源
