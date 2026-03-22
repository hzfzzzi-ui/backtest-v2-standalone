## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 通过数据库补全门禁
系统 MUST 仅在全历史回填完成、主表零行缺口成立、硬字段零空值成立且审计通过时，才允许将 `pams_ohlcv_daily_v2` 升格为正式 shadow 数据源。formal audit 的 symbol 级 `critical_exception_rows` MUST 仅统计与当前主表 `build_run_id` 对齐的有效异常；已被后续重建替换的 stale exception SHALL NOT 继续计入 gate。对于已明确归类为 known source gap 的异常，系统 MUST 在 summary 中保留暴露，但 SHALL NOT 将其计入 hard gate 使用的有效 `critical_exception_rows`。

#### Scenario: `eligible_no_source` 非零时禁止升格
- **WHEN** 全历史构建结果中仍存在任意 `eligible_no_source`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 硬字段仍有空值时禁止升格
- **WHEN** 全历史构建结果中任一硬字段仍存在空值
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: hard gate 审计未完成时禁止升格
- **WHEN** `2016-2026` 或 `2012-2017` 任一窗口缺少正式审计结果
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: stale exception 不计入 hard gate critical
- **WHEN** formal audit 扫描到某条 symbol 级异常的 `build_run_id` 已不同于当前主表同一 `symbol/trade_date` 的 `build_run_id`
- **THEN** 系统 SHALL NOT 将该异常计入 `critical_exception_rows_raw`、`known_source_gap_rows` 或 hard gate 使用的有效 `critical_exception_rows`
- **THEN** 系统 MUST 仅以当前主表仍生效的异常记录生成 formal gate summary

#### Scenario: `BJ pre daily_basic` 已知源断层不计入 hard gate critical
- **WHEN** formal audit 识别出 `turnover_rate_imputed_zero` 且 `cause_class = bj_pre_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细与 summary 中显式暴露这批样本

#### Scenario: `BJ post daily_basic` provider gap 不计入 hard gate critical
- **WHEN** formal audit 识别出 `turnover_rate_imputed_zero` 且 `cause_class = bj_post_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细与 summary 中显式暴露这批样本

#### Scenario: `pre_close` 左截断锚点缺口不计入 hard gate critical
- **WHEN** formal audit 识别出 `pre_close_imputed_zero` 且 `cause_class = left_censored_anchor_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细与 summary 中显式暴露这批样本
