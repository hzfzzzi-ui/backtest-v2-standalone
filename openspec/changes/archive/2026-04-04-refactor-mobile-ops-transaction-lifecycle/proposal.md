## Why

当前 `mobile_ops` 相关真相仍主要落在 `outputs/mobile_ops/*` 文件产物中，审批票据、执行事件、移动摘要与事务域数据库长期并存。这个状态与当前数据库正式文档已经收口的方向冲突：

- 业务事务域应成为系统运营真相层
- `transactions` 应长期收口为完整交易生命周期主表
- `outputs/` 继续只作为数据库外部产物，而不再承载正式运营真相

如果不先收这条链，移动端、桌面执行端和未来账户同步都会继续围绕文件协议扩张。

## What Changes

- 新增事务域 `transaction lifecycle` 正式能力，定义 `transactions` 作为完整交易生命周期主表的目标语义。
- 将 `mobile-order-approval`、`mobile-execution-tracking`、`mobile-daily-briefing` 的正式依赖从 `outputs/mobile_ops/*` 收回到事务域数据库。
- 明确审批、提交、成交、拒绝、撤销等状态统一并入 `transactions` 生命周期，而不是继续拆成长期文件协议。
- 保留迁移期文件产物读取/写入兼容壳，但其定位仅限过渡，不再是正式主路径。

## Capabilities

### New Capabilities
- `transaction-lifecycle-domain`: 定义事务域中完整交易生命周期主表、状态流转、来源痕迹与失败原因回显。

### Modified Capabilities
- `mobile-order-approval`: 审批动作正式写入事务域生命周期主表，而不是长期依赖 `approval_tickets` 文件协议。
- `mobile-execution-tracking`: 执行跟踪正式读取事务域状态，而不是长期依赖 `execution_events` 文件协议。
- `mobile-daily-briefing`: 移动端摘要改为基于事务域摘要视图生成，而不是把文件产物当正式真相。

## Impact

- 主要影响模块：
  - `backend/api/transactions`
  - `backend/core/services` 中移动审批/执行状态相关服务
  - `docs/02_系统架构设计/前端与移动端/mobile_semi_auto_ops.md`
- 主要风险：
  - 审批与执行状态机收口时可能遗漏旧文件字段
  - 移动端过渡期需要同时兼容数据库与文件产物
- 主要验证：
  - 生命周期状态转换单测
  - 移动摘要读取回归
  - 迁移期文件/数据库双读对照
