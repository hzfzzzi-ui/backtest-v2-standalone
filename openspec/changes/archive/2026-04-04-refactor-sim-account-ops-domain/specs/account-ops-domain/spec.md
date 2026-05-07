## ADDED Requirements

### Requirement: 账户运营子域 MUST 提供正式账户状态对象
系统 MUST 在业务事务域中提供正式账户状态对象，至少包括 `accounts`、`holdings_snapshots`、`cash_ledger`、`sync_logs`。这些对象 MUST 构成 `sim_account` 链路的正式底层真相。

#### Scenario: 查询某账户某日状态
- **WHEN** 系统查询某账户在指定日期的状态
- **THEN** 系统 MUST 能通过正式账户状态对象返回持仓快照、现金账本与同步状态
- **THEN** 调用方 SHALL NOT 需要把 `outputs/ops/sim_account/*` 作为正式主真相

### Requirement: `reconcile` MUST 仅作为派生分析结果进入数据库
系统 MUST 将 `reconcile` 定义为派生分析结果。数据库 MAY 保留摘要和引用，但 SHALL NOT 把完整 `reconcile payload` 升格为账户运营底层真相。

#### Scenario: 记录一次 reconcile 结果
- **WHEN** 系统完成一次基于账户状态和实验配置的 reconcile
- **THEN** 数据库 MAY 记录 `reconcile_id`、`account_id`、`snapshot_id`、`summary`
- **THEN** 完整 `action_sheet / diagnostics / execution_intent` SHALL 继续视为派生结果
