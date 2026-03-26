## ADDED Requirements

### Requirement: Governor 必须为 ETF beta sleeve 提供独立 deployability map
`cn-a-portfolio-governor` MUST 为 `cn_etf_beta` 提供独立 deployability map。该映射 SHALL 只消费 canonical 五状态和 Governor 总预算真相，不得直接复用股票 alpha 的 `trade_mode` 或股票局部 budget 约束。

#### Scenario: ETF beta deployability 由 Governor 单独定义
- **WHEN** Governor 计算 `cn_etf_beta` 的 sleeve budget
- **THEN** 系统 MUST 根据 canonical 五状态输出 ETF beta 的 deployable slot cap
- **THEN** 系统 SHALL NOT 直接沿用股票 alpha 的 `NO_TRADE / TREND_LIGHT / TREND_MAIN` 语义作为 ETF beta 真相

### Requirement: Governor 必须输出 ETF beta 的预算拒单原因
Governor 对 `cn_etf_beta` 的预算输出 MUST 包含最小可解释的 deployability reason codes，用于区分“状态不允许”“预算被压缩”“非调仓日保持”“候选被趋势过滤阻断”等原因。

#### Scenario: ETF beta 当日无仓位时可解释
- **WHEN** `cn_etf_beta` 在某个交易日没有生成可部署仓位
- **THEN** Governor 或 ETF beta 预算摘要 MUST 输出对应的 reason codes
- **THEN** 产物 MUST 能区分是 `state_disabled`、`budget_reduced`、`weekly_hold` 还是 `absolute_filter_blocked`
