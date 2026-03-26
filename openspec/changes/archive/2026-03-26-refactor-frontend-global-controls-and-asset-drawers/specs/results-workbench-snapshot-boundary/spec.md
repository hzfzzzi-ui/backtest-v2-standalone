## ADDED Requirements

### Requirement: 结果工作台必须按四类正式结果面板组织
当结果属于 governed A 股主线或其 ETF beta 入口时，结果工作台 MUST 至少以四类正式结果面板组织结果展示：
- `Performance`
- `Regime`
- `Governor`
- `Attribution`

这些面板 MUST 继续只消费 `ResultsWorkbenchSnapshot` 作为唯一真相源。

#### Scenario: 加载 governed A股实验结果
- **WHEN** 页面壳向结果工作台推送 governed A 股 snapshot
- **THEN** 工作台 MUST 能以 `Performance / Regime / Governor / Attribution` 的结构展示结果
- **THEN** 工作台 SHALL NOT 仅把所有 governed 字段塞入单一 overview 卡片而缺少正式面板边界

### Requirement: ResultsWorkbenchSnapshot 必须足以支持 Regime 和 Governor 独立面板
当结果工作台渲染 `Regime` 与 `Governor` 面板时，`ResultsWorkbenchSnapshot` MUST 至少提供：
- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_transition_reason`
- `risk_budget_multiplier`
- `total_risk_budget`
- `total_exposure_cap`
- `budget_reason_codes`
- `manual_override`

前端 SHALL NOT 通过旧的 `market_state`、`trade_mode` 或其他隐式字段重建这些语义。

#### Scenario: 渲染 Regime 面板
- **WHEN** 工作台打开 `Regime` 面板
- **THEN** 工作台 MUST 直接基于 snapshot 渲染正式状态与状态原因
- **THEN** 工作台 SHALL NOT 从旧字段反推出 canonical 五状态

#### Scenario: 渲染 Governor 面板
- **WHEN** 工作台打开 `Governor` 面板
- **THEN** 工作台 MUST 直接基于 snapshot 渲染预算与风险摘要
- **THEN** 工作台 SHALL NOT 在前端重算总风险预算或总暴露上限

### Requirement: ResultsWorkbenchSnapshot 必须足以支持 Attribution 面板
当结果工作台渲染 `Attribution` 面板时，`ResultsWorkbenchSnapshot` MUST 至少提供：
- `reason_codes`
- `subscores.technical`
- `subscores.sentiment`
- `subscores.macro_global`
- `manual_override.active`
- `manual_override.reason`
- `manual_override.scope`

#### Scenario: 渲染 Attribution 面板
- **WHEN** 工作台打开 `Attribution` 面板
- **THEN** 工作台 MUST 展示状态来源、预算原因和人工覆盖摘要
- **THEN** 工作台 SHALL NOT 依赖 debug 文件或额外后端请求才能渲染最小 Attribution 面板
