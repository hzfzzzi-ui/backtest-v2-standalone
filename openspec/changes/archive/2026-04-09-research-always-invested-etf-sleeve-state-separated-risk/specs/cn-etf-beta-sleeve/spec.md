## MODIFIED Requirements

### Requirement: ETF sleeve 风险角色定义
ETF sleeve MUST 支持账户层驱动的风险角色定义，并允许在研究模式下采用 always-on 的 `defense / core_beta` 分层，而不是仅在弱势环境偶发持仓。

#### Scenario: ETF sleeve consumes state-separated risk role
- **WHEN** 账户层启用 ETF always-on 研究模式
- **THEN** ETF sleeve MUST 识别 `defense` 与 `core_beta` 两类角色
- **AND** MUST 输出对应的状态分层风险解释
- **AND** MUST 保持旧 weak-state 局部逻辑仅作为 diagnostics/reference
