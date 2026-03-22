# cn-stock-v2-audit-gates Specification

## Purpose
规范 V2 canonical 的逐日审计、formal audit hard gate 与 advisory 全周期审计语义。

## Requirements

### Requirement: `v2` 构建 MUST 输出逐日审计与异常明细
系统 MUST 为 `pams_ohlcv_daily_v2` 输出逐日审计表 `pams_ohlcv_daily_v2_audit_daily` 和异常明细表 `pams_ohlcv_daily_v2_exceptions`，以覆盖行集、字段、侧表和源异常。`eligible_no_source` 与 `eligible_missing_daily_count` MUST 只反映真正无源的 `source_unresolved`；带有 side evidence 的 `synthetic_gap_fill` 与已确认 terminal 的 `delist_tail_confirmed` MUST 单列审计，而 SHALL NOT 混入 `eligible_no_source`。

#### Scenario: 逐日审计输出主表与侧表覆盖
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为窗口内每个 `trade_date` 输出 `eligible_symbol_count, raw_daily_count, v2_count, daily_basic_join_count, moneyflow_join_count, eligible_missing_daily_count, daily_basic_missing_count, moneyflow_missing_count`
- **THEN** `eligible_missing_daily_count` MUST 仅反映真 `source_unresolved`

#### Scenario: 真无源 unresolved 计入 eligible no source
- **WHEN** 某日存在 `row_status='source_unresolved'` 且缺少 `daily`、`suspend_d` 与允许的 side evidence
- **THEN** 该日 `eligible_missing_daily_count` MUST 包含这些行
- **THEN** 系统 MUST 记录 `eligible_no_source` 异常

#### Scenario: 侧证据 synthetic gap fill 不计入 eligible no source
- **WHEN** 某日存在 `row_status='synthetic_gap_fill'` 且该行保留了 side evidence
- **THEN** 该行 SHALL NOT 被计入 `eligible_missing_daily_count`
- **THEN** 系统 MUST 记录独立的 synthetic gap fill 异常，以便继续审计

#### Scenario: 显式终止尾段不计入 eligible no source
- **WHEN** 某日存在 `row_status='delist_tail_confirmed'`
- **THEN** 这些行 SHALL NOT 被计入 `eligible_missing_daily_count`
- **THEN** 系统 MUST 单列其行数与样本，供 gate 与 advisory 审计使用

### Requirement: `v2` MUST 输出 `v1/v2` 差异审计
系统 MUST 产出 `pams_ohlcv_daily` 与 `pams_ohlcv_daily_v2` 的逐日行数差异、关键字段空值差异和样本差异，以区分“覆盖修复”与“构建错误”。

#### Scenario: 逐日比较 v1 与 v2 行数
- **WHEN** 系统完成某个日期窗口的 `v2` 构建
- **THEN** 系统 MUST 为每个 `trade_date` 输出 `v1_count, v2_count, v2_minus_v1`

#### Scenario: 关键字段差异样本可追溯
- **WHEN** `v1` 与 `v2` 在某日存在显著行数或字段差异
- **THEN** 系统 MUST 输出至少一份样本明细以说明差异来自覆盖修复还是构建异常

### Requirement: `v2` 升格 MUST 通过三窗口 formal audit
系统 MUST 维护 `V2` formal audit 的固定三窗口，并仅在三窗口结果可复核时，才允许把 `pams_ohlcv_daily_v2` 视为 formal-audit-complete。固定窗口必须为：

- `2016-2026`
- `2012-2017`
- `2007-2026`

系统 SHALL NOT 继续把 `2007-2017` 作为 `V2 formal audit` 的硬门槛窗口。

#### Scenario: 三窗口 formal audit 未补齐时标记 incomplete
- **WHEN** `2016-2026`、`2012-2017`、`2007-2026` 任一窗口缺少正式 audit 产物
- **THEN** 系统 MUST 将 formal audit 状态标记为 incomplete
- **THEN** 系统 SHALL NOT 把 formal audit 视为已补齐

#### Scenario: 三窗口 formal audit 全部产出时标记 complete
- **WHEN** 系统已产出 `2016-2026`、`2012-2017`、`2007-2026` 三个窗口的正式 audit summary
- **THEN** 系统 MUST 生成一份统一 formal audit 汇总
- **THEN** 汇总 MUST 能指出每个窗口的 summary 路径和关键 gate 摘要

### Requirement: `v2` 升格 MUST 通过 formal audit hard gate
系统 MUST 将 `V2 formal audit` 区分为 hard gate windows 与 advisory windows。hard gate windows 必须为：

- `2016-2026`
- `2012-2017`

系统 MAY 继续运行 `2007-2026` 作为全周期参考审计，但 SHALL NOT 将其作为 `V2` 升格的硬门槛。

#### Scenario: hard gate formal audit 未补齐时标记 incomplete
- **WHEN** `2016-2026` 或 `2012-2017` 任一窗口缺少正式 audit 产物
- **THEN** 系统 MUST 将 hard gate formal audit 状态标记为 incomplete
- **THEN** 系统 SHALL NOT 把 formal audit hard gate 视为已补齐

#### Scenario: advisory 全周期审计不阻断 hard gate
- **WHEN** `2007-2026` 审计产物尚未生成，或仍存在待治理的全周期异常
- **THEN** 系统 MAY 将其继续作为 advisory audit 保留
- **THEN** 系统 SHALL NOT 仅因 `2007-2026` 未通过而阻断 hard gate 判定

#### Scenario: formal audit 汇总显式区分 hard gate 与 advisory
- **WHEN** 系统执行 `V2 formal audit`
- **THEN** 汇总 MUST 输出 `required_windows`
- **THEN** 汇总 MUST 输出 `advisory_windows`
- **THEN** `required_windows` SHALL ONLY 包含 `2016-2026` 与 `2012-2017`

### Requirement: `v2` 审计异常 MUST 可区分 BJ pre turnover 源缺口
系统 MUST 将 `bj_pre_20211115` 的 `turnover_rate_imputed_zero` 与笼统的映射失败区分开来。

#### Scenario: BJ pre turnover 缺口记录为 daily_basic 源缺口
- **WHEN** `bj_pre_20211115` 行在 `turnover_rate` 上未命中 `daily_basic`、AkShare 和公式 fallback
- **THEN** 系统 MUST 将该异常的 `cause_class` 记录为 `bj_pre_daily_basic_gap`
- **THEN** 异常详情 MUST 能指出 `basic_turnover` 诊断信息

### Requirement: `v2` 升格 MUST 区分已知源断层与真实 critical 构建异常
系统 MUST 在 `V2` formal audit 的 canonical gate 中，显式区分真实 hard gate critical 异常与已确认但当前没有正式免费补源的已知源断层。第一批已知源断层至少包含 `turnover_rate_imputed_zero + bj_pre_daily_basic_gap`。

#### Scenario: `BJ pre daily_basic` 已知源断层不计入 hard gate critical
- **WHEN** formal audit 在 `BJ pre-2021-11-15` 识别出 `turnover_rate_imputed_zero + bj_pre_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细和汇总里显式暴露这批样本

#### Scenario: canonical gate 同时输出 raw critical 与有效 critical
- **WHEN** 系统生成 formal audit summary
- **THEN** canonical gate MUST 输出 `critical_exception_rows_raw`
- **THEN** canonical gate MUST 输出 `known_source_gap_rows`
- **THEN** canonical gate MUST 输出剔除已知源断层后的 `critical_exception_rows`

#### Scenario: runtime 继续排除已知源断层低置信 turnover
- **WHEN** `BJ pre-2021-11-15` 的 `turnover_rate` 仍为 `imputed_zero` 且 `turnover_rate_confidence < 1`
- **THEN** runtime gate MUST 继续将其排除在 runtime 可消费集合之外
- **THEN** runtime gate MUST 将其单独标记为 `known_source_gap_low_turnover`
- **THEN** 系统 SHALL NOT 仅因这次审计语义修正而放宽 `can_consume_v10_1`

### Requirement: `v2` 升格 MUST 区分 `BJ post` 已知 provider gap 与真实 critical 构建异常
系统 MUST 将 `BJ post-2021-11-15` 的 `daily_basic.turnover_rate` 长段覆盖缺口视为已知 provider gap，而不是泛化的构建失败。第一批 `BJ post` 已知 provider gap 至少包含 `turnover_rate_imputed_zero + bj_post_daily_basic_gap`。

#### Scenario: `BJ post daily_basic` provider gap 不计入 hard gate critical
- **WHEN** formal audit 识别出 `turnover_rate_imputed_zero` 且 `cause_class = bj_post_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的有效 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细和 summary 中显式暴露这批样本

#### Scenario: runtime 继续排除 `BJ post` 已知 provider gap
- **WHEN** `BJ post-2021-11-15` 的 `turnover_rate` 仍为 `imputed_zero`，且当前行没有 `daily_basic` 或 `float_share` 支持
- **THEN** runtime gate MUST 继续将其排除在 runtime 可消费集合之外
- **THEN** runtime gate MAY 将 traded 行单独标记为 `known_source_gap_low_turnover`
- **THEN** 系统 SHALL NOT 因这次 provider gap 归类修正而放宽 `can_consume_v10_1`

### Requirement: `v2` 升格 MUST 基于真实 unresolved 缺口，而不是官方 override 已确认的 terminal 行
系统 MUST 仅把真实 `source_unresolved` 计入 `eligible_no_source`。凡是已由通用 terminal boundary 或显式官方 terminal override 确认并被分类为 `delist_tail_confirmed` 的行，系统 MUST 在 audit 中单列统计，且 SHALL NOT 继续计入 `eligible_no_source`。

#### Scenario: 显式官方 override 行不计入 eligible_no_source
- **WHEN** full-window audit 覆盖到命中显式官方 terminal override 的 `delist_tail_confirmed` 行
- **THEN** `eligible_no_source_rows` MUST 不包含这些行
- **THEN** audit summary MUST 继续单列这些行的 `delist_tail_confirmed_rows`

#### Scenario: 剩余真无源样本继续阻断 canonical gate
- **WHEN** full-window audit 结束后仍存在任意 `source_unresolved`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

### Requirement: advisory 全周期剩余 blocker MUST 只反映真实未治理样本
系统 MUST 在 advisory 全周期中区分“已被显式 terminal override 收口的连续尾段”和“仍需继续保留的真实 unresolved”。命中 pre-window pause override 的记录 SHALL NOT 继续计入 `eligible_no_source` 或有效 `critical_exception_rows`。

#### Scenario: pre-window pause override 命中的尾段不再计入 advisory blocker
- **WHEN** `2007-2026` audit 覆盖到命中 pre-window pause override 的 `delist_tail_confirmed` 行
- **THEN** 这些行 MUST 不再计入 `eligible_no_source_rows`
- **AND** 与之配对的 `pre_close_imputed_zero` 与 `turnover_rate_imputed_zero` SHALL 按既有 known source gap 规则处理
- **AND** advisory `critical_exception_rows` 只保留仍未收敛的真实 unresolved 或其他未治理异常

### Requirement: `v2` 升格 MUST 通过数据库补全门禁
系统 MUST 仅在全历史回填完成、主表零行缺口成立、硬字段零空值成立且 formal audit 通过时，才允许将 `pams_ohlcv_daily_v2` 升格为正式 shadow 数据源。formal audit 的 symbol 级 `critical_exception_rows` MUST 仅统计与当前主表 `build_run_id` 对齐的有效异常；已被后续重建替换的 stale exception SHALL NOT 继续计入 gate。对于已明确归类为 known source gap 的异常，系统 MUST 在 summary 中保留暴露，但 SHALL NOT 将其计入 hard gate 使用的有效 `critical_exception_rows`。

#### Scenario: `eligible_no_source` 非零时禁止升格
- **WHEN** 全历史构建结果中仍存在任意真 `eligible_no_source`
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
