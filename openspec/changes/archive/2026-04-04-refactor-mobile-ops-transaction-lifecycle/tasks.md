## 1. 生命周期主表与字段收口
- [x] 1.1 定义 `transactions` 生命周期主表的正式状态集合与最小字段，并与 proposal/design/spec、数据库文档保持一致。
- [x] 1.2 明确 `approval_source`、`source_intent_id`、`failure_reason_codes` 为正式回显字段，并补充对应场景说明。

## 2. mobile_ops 正式真相迁移
- [x] 2.1 将 `mobile-order-approval` 的正式落点切到统一生命周期服务，不再把 `approval_tickets` 文件视为长期正式真相。
- [x] 2.2 将 `mobile-execution-tracking` 的正式读取/推进切到统一生命周期服务，并保留迁移期 compat 写出。
- [x] 2.3 将 `mobile-daily-briefing` 收口为事务域摘要消费面，不再把 briefing 文件本身定义为底层真相。

## 3. 迁移期 compat 与验证
- [x] 3.1 明确 `outputs/mobile_ops/*` 仅作为迁移期 compat 壳，不再允许扩张为长期正式真相路径。
- [x] 3.2 补齐回归与回退说明，形成可 apply 的实现基线。
