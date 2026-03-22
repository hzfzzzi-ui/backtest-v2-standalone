## MODIFIED Requirements

### Requirement: `v2` 构建 MUST 输出逐日审计与异常明细
系统 MUST 为 `pams_ohlcv_daily_v2` 输出逐日审计表 `pams_ohlcv_daily_v2_audit_daily` 和异常明细表 `pams_ohlcv_daily_v2_exceptions`，以覆盖行集、字段、侧表和源异常。系统 MUST 将 `delist_tail_confirmed` 与真 `source_unresolved` 分开统计，且 SHALL NOT 把正式终止边界尾段混入 `eligible_no_source`。

#### Scenario: 逐日审计输出主表与侧表覆盖
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为窗口内每个 `trade_date` 输出 `eligible_symbol_count, raw_daily_count, v2_count, daily_basic_join_count, moneyflow_join_count, eligible_missing_daily_count, daily_basic_missing_count, moneyflow_missing_count`
- **THEN** `eligible_missing_daily_count` MUST 仅反映真 `source_unresolved`

#### Scenario: 异常明细记录问题类型与样本
- **WHEN** 构建过程中出现 `eligible_no_source`、`delist_tail_confirmed`、`raw_only_not_in_master`、`adj_factor_missing`、`daily_basic_missing`、`moneyflow_missing` 或软字段缺失
- **THEN** 系统 MUST 在异常表中记录 `trade_date, symbol, ts_code, issue_type, issue_detail, source_table, build_run_id`

### Requirement: `v2` 升格 MUST 通过数据库补全门禁
系统 MUST 仅在全历史回填完成、主表零行缺口成立、硬字段零空值成立且审计通过时，才允许将 `pams_ohlcv_daily_v2` 升格为正式 shadow 数据源。

#### Scenario: `eligible_no_source` 非零时禁止升格
- **WHEN** 全历史构建结果中仍存在任意真 `eligible_no_source`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 终止尾段单列但不算真无源
- **WHEN** 全历史构建结果中存在 `delist_tail_confirmed`
- **THEN** 系统 MUST 单列其行数与样本
- **THEN** 系统 SHALL NOT 仅因 `delist_tail_confirmed` 非零而把 canonical 判为“真无源未清零”

#### Scenario: 硬字段仍有空值时禁止升格
- **WHEN** 全历史构建结果中任一硬字段仍存在空值
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 三窗口审计未完成时禁止升格
- **WHEN** `2016-2026`、`2007-2017`、`2007-2026` 任一窗口缺少正式审计结果
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源
