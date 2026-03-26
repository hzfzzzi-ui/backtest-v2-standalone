## ADDED Requirements

### Requirement: Governor 最新快照必须保留 ETF 资产语义
当 `asset_scope=cn_etf` 的运行写出 Governor budget 摘要时，系统 MUST 在 `run_meta` 与 `audit` 的最新快照中保留 ETF 资产语义、ETF budget consumer 和 ETF sleeve 摘要，系统 SHALL NOT 将其退化为 `cn_a_equity / cn_stock_trend_alpha_core` 默认语义。

#### Scenario: ETF 运行导出 Governor latest
- **WHEN** `cn_etf` 运行完成并生成 `audit.json`
- **THEN** `governor_budget.latest.asset_scope` MUST 等于 `cn_etf`
- **THEN** `governor_budget.latest.budget_consumer_sleeve_id` MUST 与 ETF sleeve 真相一致

