## MODIFIED Requirements

### Requirement: 自动同步 MUST 写入账户运营子域正式对象
系统 MUST 将自动同步正式写入账户运营子域中的 `holdings_snapshots`、`cash_ledger` 和 `sync_logs`，而不是长期以文件产物作为主真相。

#### Scenario: 每日自动同步完成
- **WHEN** 系统完成一次 sim account 自动同步
- **THEN** 系统 MUST 写入或更新持仓快照、现金账本和同步日志
- **THEN** 文件镜像 MAY 继续存在，但 SHALL NOT 替代数据库真相
