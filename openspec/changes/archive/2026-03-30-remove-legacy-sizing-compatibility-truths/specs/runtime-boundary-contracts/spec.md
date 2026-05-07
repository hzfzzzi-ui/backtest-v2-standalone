## MODIFIED Requirements

### Requirement: 执行链必须只有一套 sizing 真相
系统 MUST 在正式执行链中维护唯一的 sizing 真相。`candidate_plan`、`execution_orders` 和兼容入口 `build_rebalance_orders()` SHALL NOT 各自保留独立的目标金额/数量计算实现。

#### Scenario: stage 主链生成执行订单
- **WHEN** 系统基于已确认的 `planned_items` 生成执行订单
- **THEN** `candidate_plan` 与 `execution_orders` MUST 复用同一套共享 sizing 计算
- **THEN** 系统 SHALL NOT 在后续兼容入口中再次实现第二套 sizing 公式

#### Scenario: 历史兼容入口仍被调用
- **WHEN** 非 stage 路径继续调用 `build_rebalance_orders()`
- **THEN** 该入口 MUST 仅编排 `candidate_plan -> execution_orders`
- **THEN** 该入口 SHALL NOT 再保留独立的 sizing 真相

### Requirement: 兼容入口必须收敛为薄编排层
系统 MAY 保留 `build_rebalance_orders()` 作为历史调用入口，但该入口 MUST 是薄编排层，而不是独立执行算法。

#### Scenario: build_rebalance_orders 处理买卖计划
- **WHEN** 调用方通过 `build_rebalance_orders()` 构建订单
- **THEN** 系统 MUST 先形成 `candidate_plan_v1`
- **THEN** 系统 MUST 再基于共享 sizing 真相生成执行订单
- **THEN** 兼容入口 SHALL 只负责合并 audit/debug 摘要
