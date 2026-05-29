## ADDED Requirements

### Requirement: reconcile run SHALL only be package source, not asset truth
`position-aware-reconcile-run` 的 action sheet 可以作为 `daily_position_adjustment_package@1` 的来源输入，但 reconcile run SHALL 继续定义为派生分析结果。系统 MUST NOT 将完整 reconcile payload 升格为账户、持仓或交易生命周期真值。

#### Scenario: 从 reconcile 生成调仓包
- **WHEN** live strategy run 使用最新持仓快照完成 reconcile
- **THEN** 系统 MAY 从 reconcile action sheet 构造调仓包
- **THEN** 调仓包 MUST 记录 `reconcile_id` 和 `holdings_snapshot_id`
- **THEN** 账户和交易真值 MUST 仍由 PAMS 事务域持有

### Requirement: stale reconcile SHALL NOT publish package
当 reconcile run 被标记为 `stale`、`drifted` 或市场/持仓输入不满足 fresh 条件时，系统 SHALL NOT 发布正式调仓包。

#### Scenario: 新持仓快照使 reconcile 失效
- **WHEN** reconcile run 生成后出现更新的同账户持仓快照
- **THEN** 旧 reconcile run MUST 被视为 stale 或 drifted
- **THEN** 系统 SHALL NOT 基于旧 reconcile run 发布正式调仓包
