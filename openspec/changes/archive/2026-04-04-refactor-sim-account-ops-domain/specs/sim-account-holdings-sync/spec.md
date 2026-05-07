## MODIFIED Requirements

### Requirement: 持仓同步 MUST 以持仓快照作为正式返回面
系统 MUST 将持仓同步的正式返回面定义为 `holdings_snapshots`，而不是长期依赖文件形式的 holdings 记录。

#### Scenario: 更新当日持仓快照
- **WHEN** 系统同步到一份新的账户持仓
- **THEN** 系统 MUST 在正式持仓快照对象中记录该状态
- **THEN** 快照结果 MUST 能提供 `qty` 与 `sellable_qty` 等正式字段
