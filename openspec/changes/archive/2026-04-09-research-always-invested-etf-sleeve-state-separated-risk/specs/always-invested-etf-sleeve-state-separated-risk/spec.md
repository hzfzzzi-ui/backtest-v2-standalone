## ADDED Requirements

### Requirement: ETF sleeve shall support always-on state-separated risk allocation
系统 MUST 支持一条研究能力：ETF sleeve 在所有账户状态下保持非零持仓，并在 `defense` 与 `core_beta` 之间按状态切换风险分层。

#### Scenario: ETF sleeve remains non-zero across states
- **WHEN** 账户层进入任一有效状态
- **THEN** 系统 MUST 为 ETF sleeve 生成非零目标持仓语义
- **AND** MUST 明确区分 `defense` 与 `core_beta` 的状态分层

### Requirement: ETF sleeve shall not become a second stock risk sleeve
系统 MUST 约束 ETF sleeve 的 always-on 研究语义，以避免其变成第二条高 beta 股票腿。

#### Scenario: Defensive state keeps defense dominant
- **WHEN** 账户层进入 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 系统 MUST 令 ETF sleeve 的 `defense` 预算不低于 `core_beta`
- **AND** MUST 保留 `core_beta` 仅为少量配置角色
