## ADDED Requirements

### Requirement: 系统必须维护标准化模拟盘持仓快照
系统 MUST 接收模拟盘持仓输入并落地为标准化快照。标准化快照 SHALL 至少包含 `account_id`、`snapshot_id`、`trade_date`、`synced_at`、`source_type`、`cash` 和 `positions[]`。`positions[]` 中的每一行 MUST 至少包含 `symbol`、`qty`、`sellable_qty`、`avg_cost`，并使用系统统一的 symbol 规范。

#### Scenario: 成功写入一份新的模拟盘持仓快照
- **WHEN** 系统收到一份字段完整、symbol 可解析的模拟盘持仓输入
- **THEN** 系统 SHALL 生成新的 `snapshot_id`
- **THEN** 系统 SHALL 同时写入 `holdings/history/<snapshot_id>.json` 和 `holdings/latest.json`

#### Scenario: 无效持仓输入不会覆盖当前真相
- **WHEN** 持仓输入缺少关键字段、symbol 无法标准化，或 `qty/avg_cost` 不合法
- **THEN** 系统 SHALL 拒绝本次写入并返回显式失败状态
- **THEN** 系统 SHALL NOT 覆盖现有 `holdings/latest.json`

### Requirement: 系统必须暴露模拟盘持仓同步状态
系统 MUST 维护可供手机端和桌面端读取的持仓同步状态。该状态 SHALL 至少返回 `status`、`account_id`、`latest_snapshot_id`、`trade_date`、`synced_at`、`age_seconds` 和 `warnings`。当系统没有任何成功快照时，状态 MUST 返回显式 `unsynced` 或等价状态，而 SHALL NOT 伪造“当前持仓”。

#### Scenario: 已存在最新成功快照
- **WHEN** 系统已有某账户的最新成功持仓快照
- **THEN** 同步状态 SHALL 返回该快照的 `latest_snapshot_id`、`trade_date` 和 `synced_at`
- **THEN** 手机端当前持仓 SHALL 以该快照为唯一来源

#### Scenario: 尚未同步任何持仓
- **WHEN** 账户还没有任何成功快照
- **THEN** 同步状态 MUST 返回 `unsynced`
- **THEN** 手机端 SHALL 显式提示“当前持仓未同步”，而不是回退到实验成交推导持仓

### Requirement: 系统必须保留持仓同步审计和漂移信息
系统 MUST 为每次持仓同步记录 append-only 审计事件，并在新快照与上一份最新快照或待执行 ticket 发生差异时输出漂移信息。漂移信息 SHALL 至少能区分“仓位数量变化”“标的增删变化”和“存在未消费 ticket 期间发生的账户变动”。

#### Scenario: 新快照与上一份快照存在仓位差异
- **WHEN** 新持仓快照与上一份最新快照相比，某些 symbol 的数量或持仓集合发生变化
- **THEN** 系统 SHALL 记录 drift 摘要
- **THEN** 后续 reconcile 结果 SHALL 能引用这份 drift 信息

#### Scenario: 待执行 ticket 存在时同步了新持仓
- **WHEN** 系统中仍有 `approved_pending` ticket，且账户又同步了新的持仓快照
- **THEN** 系统 SHALL 记录“pending ticket期间持仓变化”的审计事件
- **THEN** 旧 reconcile 结果 SHALL 被标记为可能失效或需要重算
