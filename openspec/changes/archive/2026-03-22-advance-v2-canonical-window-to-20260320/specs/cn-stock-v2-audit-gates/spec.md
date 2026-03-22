## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 通过数据库补全门禁
系统 MUST 仅在全历史回填完成、主表零行缺口成立、硬字段零空值成立且审计通过时，才允许将 `pams_ohlcv_daily_v2` 升格为正式 shadow 数据源。系统 MUST 基于当前 official window 判断 `has_full_window`，并在审计总结中显式输出 official window 的起止边界，避免 stale window 造成误判。

#### Scenario: `eligible_no_source` 非零时禁止升格
- **WHEN** 全历史构建结果中仍存在任意 `eligible_no_source`
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 硬字段仍有空值时禁止升格
- **WHEN** 全历史构建结果中任一硬字段仍存在空值
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 三窗口审计未完成时禁止升格
- **WHEN** `2016-2026`、`2007-2017`、`2007-2026` 任一窗口缺少正式审计结果
- **THEN** 系统 SHALL NOT 将 `pams_ohlcv_daily_v2` 视为正式 shadow 数据源

#### Scenario: 审计窗口未覆盖当前正式窗口时标记非 full-window
- **WHEN** 审计起止边界不等于当前 official window
- **THEN** 审计总结中的 `has_full_window` MUST 为 `false`
- **THEN** 系统 SHALL NOT 将该次审计结果表述为正式 full-window gate

#### Scenario: 审计总结暴露正式窗口边界
- **WHEN** 系统输出 `v2` 审计总结
- **THEN** 总结 MUST 输出 `official_window.start` 与 `official_window.end`
- **THEN** 用户 MUST 无需阅读源码即可判断 `has_full_window` 是按哪个正式窗口计算
