## MODIFIED Requirements

### Requirement: Shared runtime shall explain always-on ETF state-separated execution
共享账户执行 runtime MUST 为 ETF always-on 研究模式提供状态分层执行解释，并保持账户层单一主叙事。

#### Scenario: Shared runtime exposes ETF always-on explain
- **WHEN** ETF always-on 研究模式启用
- **THEN** 系统 MUST 在主 runtime 中输出 ETF sleeve 的 `defense / core_beta` 状态分层 explain
- **AND** MUST 保持 shared account runtime 为主 execution owner
- **AND** MUST 将旧 weak-state 路径保留为 diagnostics/reference
