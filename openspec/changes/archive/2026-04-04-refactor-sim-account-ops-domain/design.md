## Context

当前 `sim_account` 链路把下列对象混在一起：

- 账户状态与持仓快照
- 现金池刷新/修补
- 同步与对账日志
- `reconcile` 生成的建议面与 action sheet

而文档层已经明确，这几类对象不应再同层：

- 账户主数据 / 持仓快照 / 现金账本 / 同步日志 属于事务域正式真相
- `reconcile` 只是基于这些真相与实验结果生成的派生分析结果

本次 change 是 L2 架构收口：专注 `sim_account` 账户运营域，不碰移动审批生命周期主表，也不碰前端新壳。

## Goals / Non-Goals

**Goals**

- 定义账户运营子域的正式对象边界
- 将持仓快照与现金账本收回数据库
- 将同步/对账日志收回数据库
- 将 `reconcile` 收口为摘要/引用对象

**Non-Goals**

- 不在本次 change 中重构移动审批与执行状态机
- 不在本次 change 中改变 `baseline_V10.1` 研究逻辑
- 不在本次 change 中搬迁 `outputs/experiments/*`

## Decisions

### 1. 账户运营子域采用四类正式对象

正式对象至少包括：

- `accounts`
- `holdings_snapshots`
- `cash_ledger`
- `sync_logs`

### 2. 持仓与现金不再长期依赖文件产物

迁移后：

- 持仓快照必须能作为正式数据库对象查询
- 现金变化必须记录到 `cash_ledger`
- 同步与对账必须落到 `sync_logs`

### 3. `reconcile` 只保留摘要/引用

数据库中的 `reconcile` 相关对象只保留：

- `reconcile_id`
- `account_id`
- `snapshot_id`
- `exp_id` 或配置引用
- `generated_at`
- `summary`
- 新鲜度/状态

完整 `action_sheet / diagnostics / execution_intent` 继续视为派生产物，而不是账户运营底层真相。

## Risks / Trade-offs

- 旧服务可能仍以文件存在性作为状态判断
- `cash_ledger` 和 `sync_logs` 的边界需要避免重叠
- `reconcile` 降级后，上层需要显式区分“正式真相”和“操作建议”

## Migration Plan

1. 先定义账户运营子域正式对象
2. 迁 `holdings_snapshots`
3. 迁 `cash_ledger` 与 `sync_logs`
4. 把 `reconcile` 收成摘要/引用
5. 最后收紧 `outputs/ops/sim_account/*` 为过渡 compat，并明确退出条件：
   - 主服务不再把 compat 文件当正式主读路径
   - 桌面/移动消费者切到账户运营域对象或 `reconcile summary`
   - 详细 `reconcile payload` 不再承担同步真相职责
   - 已完成一轮以账户运营域为主的回归与回退验证

## Rollback

- 保留迁移期文件镜像写出
- 若数据库对象不稳定，可临时回退为数据库镜像 + 文件主读
- 回退顺序固定为：先关闭自动同步，再恢复 compat 主读，最后按需回放历史镜像
