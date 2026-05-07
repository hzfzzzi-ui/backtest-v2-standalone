## ADDED Requirements

### Requirement: 结果 snapshot 正式由桌面 app state 持有
系统 SHALL 将结果 snapshot 的正式所有权收口到桌面 app state，bridge 只允许作为迁移期壳间通信工具存在。

#### Scenario: bridge 不再是正式 snapshot owner
- **WHEN** 系统描述结果 snapshot 的正式所有权
- **THEN** 正式 owner MUST 是桌面 app state 而不是 bridge
