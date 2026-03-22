## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 基于真实 unresolved 缺口，而不是官方 override 已确认的 terminal 行
系统 MUST 仅把真实 `source_unresolved` 计入 `eligible_no_source`。凡是已由通用 terminal boundary 或显式官方 terminal override 确认并被分类为 `delist_tail_confirmed` 的行，系统 MUST 在 audit 中单列统计，且 SHALL NOT 继续计入 `eligible_no_source`。

#### Scenario: 显式官方 override 行不计入 eligible_no_source
- **WHEN** full-window audit 覆盖到命中显式官方 terminal override 的 `delist_tail_confirmed` 行
- **THEN** `eligible_no_source_rows` MUST 不包含这些行
- **THEN** audit summary MUST 继续单列这些行的 `delist_tail_confirmed_rows`

#### Scenario: 剩余真无源样本继续阻断 canonical gate
- **WHEN** full-window audit 结束后仍存在任意 `source_unresolved`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源
