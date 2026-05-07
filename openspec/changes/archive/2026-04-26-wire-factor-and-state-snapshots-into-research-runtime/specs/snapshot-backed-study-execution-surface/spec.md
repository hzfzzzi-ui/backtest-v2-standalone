## ADDED Requirements

### Requirement: Snapshot-backed study execution surface
系统 SHALL 提供 snapshot-backed study execution surface，使研究 runner 可以声明 snapshot 输入、窗口、variant 和研究模式，并在不触发完整策略回放的前提下运行研究。

#### Scenario: study runner 可声明 snapshot 输入
- **WHEN** study 定义包含 snapshot 输入引用
- **THEN** 系统 SHALL 能解析并加载对应 snapshot 输入

#### Scenario: runtime 不依赖完整策略回放
- **WHEN** snapshot-backed study execution 被触发
- **THEN** 系统 SHALL 能在不运行完整策略回放的情况下输出研究结果
