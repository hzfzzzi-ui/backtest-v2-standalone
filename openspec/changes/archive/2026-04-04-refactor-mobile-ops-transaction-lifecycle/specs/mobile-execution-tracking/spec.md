## MODIFIED Requirements

### Requirement: 移动执行跟踪 MUST 读取事务生命周期状态
系统 MUST 以事务域中的 `transactions` 生命周期状态作为移动执行跟踪的正式来源，而不是长期读取 `outputs/mobile_ops/execution_events/*` 文件协议。

#### Scenario: 查看一笔交易的执行推进
- **WHEN** 用户查看某笔已审批交易的执行状态
- **THEN** 系统 MUST 返回来自 `transactions` 生命周期主表的正式状态
- **THEN** 返回结果 MUST 能区分 `submitted`、`partially_filled`、`filled`、`rejected`、`cancelled`
