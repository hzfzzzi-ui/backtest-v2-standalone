## ADDED Requirements

### Requirement: 系统必须正式解析 `cn_etf` canonical asset profile
系统 MUST 允许请求入口、runtime compile、manifest 和 snapshot 正式解析 `asset_scope='cn_etf'`，并输出稳定的 `asset_context`。该 `asset_context` MUST 至少包含 `asset_scope`、`asset_profile_id`、`asset_family`、`asset_class`、`market_profile_id` 和 `execution_profile_id`。

#### Scenario: 解析 A 股 ETF 资产边界
- **WHEN** 运行请求、study 或历史 manifest 显式声明 `asset_scope='cn_etf'`
- **THEN** 系统 MUST 解析出 canonical ETF `asset_context`
- **THEN** 该 `asset_context` MUST 不得回退为 `cn_a_equity`

#### Scenario: ETF 入口沿用中国大陆市场执行壳
- **WHEN** 系统解析 `cn_etf` 资产范围
- **THEN** `asset_context` MUST 暴露中国大陆市场交易日历和 `T+1 / NEXT_OPEN / lot=100` 的执行语义
- **THEN** 系统 MUST 不把股票特有过滤或股票池语义当成 ETF 默认真相
