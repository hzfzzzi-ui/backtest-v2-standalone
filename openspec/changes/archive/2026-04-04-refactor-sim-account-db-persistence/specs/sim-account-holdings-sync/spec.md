## ADDED Requirements

### Requirement: holdings sync 正式写入持仓快照
系统 SHALL 将 `sim-account-holdings-sync` 的正式结果写入 `holdings_snapshots` 对象，而不再把文件型 holdings latest/history 视为长期主真相。

#### Scenario: holdings sync 生成正式快照
- **WHEN** 系统完成一次持仓同步
- **THEN** 正式持仓状态 MUST 通过持仓快照对象可读
