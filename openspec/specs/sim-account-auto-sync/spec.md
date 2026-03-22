## ADDED Requirements

### Requirement: 模拟盘持仓必须支持定时文件导入
系统 MUST 支持从可配置 JSON 文件路径自动导入模拟盘真实持仓，并将其标准化为 sim account holdings snapshot。导入器 SHALL 至少支持 `account_id`、`trade_date`、`cash`、`positions[]` 字段，并复用现有 snapshot 标准化校验。

#### Scenario: 导入器读取有效持仓文件
- **WHEN** 定时任务读取到合法的持仓 JSON 文件
- **THEN** 系统 MUST 调用标准化 snapshot 写入逻辑生成新的 holdings snapshot
- **AND** 新 snapshot MUST 写入 `holdings/latest.json` 与 history

#### Scenario: 导入文件非法时不得覆盖最新快照
- **WHEN** 持仓文件缺字段、symbol 非法或数量无效
- **THEN** 系统 MUST 记录自动同步失败状态
- **AND** 系统 SHALL NOT 覆盖现有 `holdings/latest.json`

### Requirement: 持仓自动导入后必须自动重跑 reconcile
当定时导入成功写入新的 holdings snapshot 后，系统 MUST 自动触发 position-aware reconcile，并使用本次调度目标交易日作为默认 `strategy_as_of_date`。

#### Scenario: 导入成功后刷新 trade sheet
- **WHEN** 新 holdings snapshot 写入成功，且其 `trade_date` 不晚于本次市场同步目标日
- **THEN** 系统 MUST 自动执行 reconcile
- **AND** `reconcile/latest.json` MUST 绑定该 snapshot_id

#### Scenario: 导入日期落后时显式降级
- **WHEN** 导入文件 `trade_date` 早于本次市场同步目标日
- **THEN** 系统 MUST 将自动同步状态标记为 stale_input 或等价显式状态
- **AND** 系统 MAY 保留旧 reconcile，但 SHALL NOT 伪造“已刷新到最新”

### Requirement: 自动同步状态必须可观测
系统 MUST 维护独立的模拟盘自动同步状态对象，至少包含 `status`、`account_id`、`source_path`、`snapshot_id`、`trade_date`、`synced_at`、`reconcile_id`、`message` 与 `updated_at`，供 mobile/desktop 或运维诊断读取。

#### Scenario: 成功同步后记录状态
- **WHEN** 持仓自动导入与 reconcile 均成功
- **THEN** 状态对象 MUST 返回 `success`
- **AND** 包含本次 `snapshot_id` 与 `reconcile_id`

#### Scenario: 文件缺失时显式记录失败
- **WHEN** 自动同步路径未配置或目标文件不存在
- **THEN** 状态对象 MUST 返回 `disabled` 或 `failed`
- **AND** `message` MUST 包含可读原因
