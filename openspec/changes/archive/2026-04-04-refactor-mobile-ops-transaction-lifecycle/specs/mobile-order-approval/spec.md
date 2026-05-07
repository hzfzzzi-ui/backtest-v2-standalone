## MODIFIED Requirements

### Requirement: 移动审批 MUST 写入事务生命周期主表
系统 MUST 将移动审批的正式落点定义为事务域数据库中的 `transactions` 生命周期主表，而不是长期依赖 `outputs/mobile_ops/approval_tickets/*` 作为正式真相。

#### Scenario: 移动审批生成待提交交易
- **WHEN** 用户在移动端确认一笔买入或卖出动作
- **THEN** 系统 MUST 在 `transactions` 中生成或更新相应生命周期记录
- **THEN** 迁移期 MAY 同步写出文件产物，但该文件 SHALL NOT 被定义为正式真相
