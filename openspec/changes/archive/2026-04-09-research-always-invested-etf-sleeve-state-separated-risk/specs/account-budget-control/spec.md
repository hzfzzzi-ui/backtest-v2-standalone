## MODIFIED Requirements

### Requirement: 账户层预算控制 shall support always-on ETF risk budgets
账户层预算控制 MUST 支持 ETF sleeve 的 always-on 风险分层预算，并继续作为唯一预算真相。

#### Scenario: Account budget distinguishes ETF defense and core beta
- **WHEN** 账户层启用 ETF always-on 研究模式
- **THEN** 系统 MUST 在预算控制中区分 ETF 的 `defense` 与 `core_beta` 预算
- **AND** MUST 在所有状态下保持 ETF sleeve 的非零预算语义
