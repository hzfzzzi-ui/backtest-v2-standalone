## MODIFIED Requirements

### Requirement: `v2` 审计异常 MUST 可区分 BJ pre turnover 源缺口
系统 MUST 将 `bj_pre_20211115` 的 `turnover_rate_imputed_zero` 与笼统的映射失败区分开来。

#### Scenario: BJ pre turnover 缺口记录为 daily_basic 源缺口
- **WHEN** `bj_pre_20211115` 行在 `turnover_rate` 上未命中 `daily_basic`、AkShare 和公式 fallback
- **THEN** 系统 MUST 将该异常的 `cause_class` 记录为 `bj_pre_daily_basic_gap`
- **THEN** 异常详情 MUST 能指出 `basic_turnover` 诊断信息
