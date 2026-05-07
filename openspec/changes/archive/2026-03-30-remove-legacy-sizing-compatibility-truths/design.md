## Design Overview

这条 change 只解决两个正式边界问题：

1. 执行链中只能存在一套 sizing 真相。
2. 正式审计中不能再保留 `sleeve_budget` 历史别名。

范围不包含：

- ETF 私有层减法收敛
- `order_planning` 以外的新执行合同
- 任何收益优化

## Target State

正式执行链收敛为：

`candidate_boundary_v1 -> candidate_plan_v1 -> shared sizing truth -> execution_orders -> target_book_v1`

其中：

- `candidate_plan.py` 负责候选规划和形成已确认的 `planned_items`
- 共享 sizing helper 负责把 `planned_items` 转成执行级目标金额/数量
- `execution_orders.py` 只消费共享 sizing 结果生成正式订单
- `build_rebalance_orders()` 只做兼容编排，不再自行实现第二套 sizing 算法

正式审计收敛为：

- `candidate_boundary`
- `candidate_plan`
- `execution_kernel`

不再提供：

- `sleeve_budget`

## Implementation Notes

### Shared sizing truth

需要抽出共享 helper，至少统一这些计算：

- `target_weight` 直达目标金额
- `base_order_value / min_positions / max_positions` 的 sizing 基数
- `risk_amount + ATR` 风险预算 sizing
- `inverse_vol` 权重归一
- 最终 `target_amount_scaled / qty / cost`

### Thin legacy orchestration

`build_rebalance_orders()` 继续保留函数名，仅作为兼容入口：

- 先调用 `build_candidate_plan(...)`
- 再调用 `build_execution_orders_from_candidate_plan(...)`
- 合并 `candidate_audit`
- 合并 `debug_plan`

它不得再维护独立 sizing 真相。

### Formal audit cleanup

`daily_accounting.py` 中的 audit row 继续保留三层正式摘要，但删除：

- `audit_row["sleeve_budget"]`

这样正式审计与当前架构文档保持一致，不再暴露历史别名。
