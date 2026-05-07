## Context

当前移动半自动链路主要由下列文件产物驱动：

- `outputs/mobile_ops/approval_tickets/*`
- `outputs/mobile_ops/execution_events/*`
- `outputs/mobile_ops/daily_briefings/*`

而事务域数据库目前只有较薄的 `transactions` 记录能力，没有形成统一的生命周期主表。文档层已经明确：

- `transactions` 长期目标是完整交易生命周期主表
- `approval_tickets` 和 `execution_events` 长期应并入事务域数据库
- 移动端正式角色应收回为只读摘要 + 快速查看结果

本次 change 是 L2 架构收口：先把 `mobile_ops` 的正式真相回收到事务域，不碰前端新壳，不碰 `sim_account` 账户运营域。

## Goals / Non-Goals

**Goals**

- 定义 `transactions` 生命周期主表的正式状态集合与最小字段
- 把移动审批与执行跟踪正式绑定到事务域数据库
- 为移动端保留只读摘要能力，但其来源改为事务域摘要视图
- 明确迁移期 compat：允许文件产物继续存在，但只作为过渡壳

**Non-Goals**

- 不在本次 change 中重构 `sim_account` 持仓、现金与对账链
- 不在本次 change 中重做移动端 UI
- 不在本次 change 中改变研究逻辑或执行策略口径
- 不在本次 change 中处理通知系统

## Decisions

### 1. `transactions` 成为完整交易生命周期主表

正式事务对象必须覆盖至少以下生命周期状态语义：

- `draft_requested`
- `approved_pending_submission`
- `submitted`
- `partially_filled`
- `filled`
- `rejected`
- `cancelled`

同时必须保留：

- `account_id`
- `symbol`
- `side`
- `requested_qty`
- `filled_qty`
- `price / avg_fill_price`
- `source_intent_id`
- `approval_source`
- `failure_reason_codes`

### 2. 审批与执行事件不再长期以独立文件协议作为主真相

迁移后：

- 审批动作写入 `transactions`
- 执行状态推进写回 `transactions`
- 如需保留事件流，可作为从表或审计表，但仍属事务域数据库

### 3. `daily_briefing` 只保留摘要语义

`daily_briefing` 不再被定义为事务真相对象，而是事务域摘要视图的下游消费面。它可以继续生成文件/缓存，但正式真相应回到数据库。

## Risks / Trade-offs

- 旧移动端流程可能仍隐式依赖文件路径与文件命名规则
- `transactions` 状态机一旦定义过粗，会影响后续桌面执行与对账
- 迁移期双写/双读会增加实现复杂度

## Migration Plan

1. 先定义事务域生命周期主表与移动能力的 delta specs
2. 第一批实现先让审批写入 `transactions`
3. 第二批实现把执行跟踪改为读写事务状态
4. 第三批实现把 `daily_briefing` 改为基于事务摘要生成
5. 最后收紧 `outputs/mobile_ops/*` 为过渡 compat

## Rollback

- 保留迁移期文件协议写出能力
- 若数据库链路不稳定，可临时回退为文件主读 + 数据库镜像写入
