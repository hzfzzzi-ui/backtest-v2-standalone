## MODIFIED Requirements

### Requirement: 执行合同黄金样例 MUST 覆盖正式边界关键场景
系统 MUST 提供覆盖正式执行边界的黄金样例，至少覆盖：普通 `BUY/SELL`、`REDUCE_ONLY`、`FORCE_EXIT`、优先级跳过、整手取整变 0、卖出截断到 `sellable_qty`、普通动作与 override 同日并存。

#### Scenario: 普通 SELL 与 symbol FORCE_EXIT 同日并存
- **WHEN** 同一标的同日同时存在普通 `SELL` 和 `symbol FORCE_EXIT`
- **THEN** goldens MUST 覆盖“普通 SELL 先执行，不足部分再由 FORCE_EXIT 补足”的正式语义
- **THEN** goldens MUST 覆盖对应的 `execution_audit` 回显
