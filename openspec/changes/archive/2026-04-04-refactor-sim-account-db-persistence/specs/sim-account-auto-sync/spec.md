## ADDED Requirements

### Requirement: auto sync 正式写入现金账本与同步日志
系统 SHALL 将 `sim-account-auto-sync` 的正式写入结果收口到 `cash_ledger` 与 `sync_logs`，而不是长期写入文件型 latest/history 真相。

#### Scenario: auto sync 完成后生成正式账户运营记录
- **WHEN** 自动同步完成一次账户刷新
- **THEN** 系统 MUST 更新正式现金账本与同步日志对象
