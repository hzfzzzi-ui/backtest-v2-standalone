## ADDED Requirements

### Requirement: sim_account 正式对象进入业务事务域数据库
系统 SHALL 将 `accounts`、`holdings_snapshots`、`cash_ledger` 与 `sync_logs` 定义为 `sim_account` 在业务事务域中的正式数据库对象，而不再长期依赖 `outputs/ops/sim_account/*` 文件路径。

#### Scenario: 账户状态正式从数据库对象读取
- **WHEN** 系统需要读取某个模拟账户的当前持仓与现金状态
- **THEN** 正式读取路径 MUST 来自事务域数据库对象

### Requirement: reconcile 只保留摘要与引用
系统 SHALL 将 `reconcile` 定义为派生分析结果，只允许 `reconcile_summary` 或引用索引进入正式事务域对象。

#### Scenario: reconcile 不再充当底层真相
- **WHEN** 系统需要展示最近一次 reconcile 结果
- **THEN** 正式数据库对象 MUST 只返回摘要与引用，而不是完整派生 payload

### Requirement: compat 文件只作为迁移期影子写出
系统 SHALL 允许迁移期继续保留 `outputs/ops/sim_account/*` 影子写出，但 compat 文件 MUST 不再定义正式读取边界。

#### Scenario: 数据库真相优先于 compat 文件
- **WHEN** 数据库对象与 compat 文件同时存在
- **THEN** 正式读取路径 MUST 优先使用数据库对象
