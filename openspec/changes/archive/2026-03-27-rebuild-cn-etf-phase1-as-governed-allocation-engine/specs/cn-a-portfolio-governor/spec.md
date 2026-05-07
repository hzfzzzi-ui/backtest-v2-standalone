## ADDED Requirements

### Requirement: Governor 必须以正式预算 contract 约束 ETF Phase 1 配置引擎
`global_portfolio_governor` MUST 向 ETF Phase 1 正式主线下发最小正式预算 contract，至少包括总 ETF sleeve 可用预算、暴露上限、执行约束与防守偏置，且 ETF 本地无权绕过这份 contract 独立上仓。

#### Scenario: Governor 下发 ETF Phase 1 预算边界
- **WHEN** Governor 为某个交易日计算 A 股组合 sleeve budget
- **THEN** ETF Phase 1 MUST 消费 Governor 下发的 ETF 预算边界
- **THEN** ETF Phase 1 SHALL NOT 自行放大超出 Governor 下发的总风险与总暴露

### Requirement: Governor 必须允许 ETF Phase 1 在边界内完成本地分配
Governor MUST 只定义 ETF Phase 1 的总预算边界和防守偏置，不得把 ETF 内部三桶分配和桶内配置直接硬编码为与个股 alpha 相同的部署语义。

#### Scenario: Governor 与 ETF 本地分配边界清晰
- **WHEN** ETF Phase 1 在 Governor 预算内生成 `equity_core_bucket`、`defense_tilt_bucket` 与 `cash_buffer_bucket`
- **THEN** Governor 审计 MUST 能区分“总预算边界”和“ETF 本地分配决策”
- **THEN** ETF 本地分配结果 MUST 继续服从 Governor 下发的总预算与执行限制
