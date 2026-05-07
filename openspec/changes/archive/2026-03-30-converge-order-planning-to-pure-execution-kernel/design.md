## Context

当前正式执行链已经存在三层合同：

1. `candidate_boundary_v1`
2. `candidate_plan_v1`
3. `target_book_v1`

但 `order_planning` 仍未完全收敛为纯执行内核，主要残留两类问题：

- 当 `runtime._current_day` 缺少 `candidate_boundary` 或 `candidate_plan` 时，`order_planning` 仍会自行回退构建。
- `order_planning` 仍通过旧的 `build_rebalance_orders()` 路径传入一组被“中和”的候选规划兼容参数，这意味着共享执行层仍然依赖候选规划接口形状。

这会导致：

- 上游 `bridge_adapter.ensure_day()` 已经建立的阶段边界被下游重新打穿。
- 共享执行层看起来已经收敛，但实际上仍和个股子系统的候选规划兼容逻辑绑在一起。

## Goals / Non-Goals

**Goals**

- 让 `order_planning` 只消费上游已准备好的 `candidate_plan_v1` 与执行级必要参数。
- 增加一条纯执行级下单辅助路径，只负责把“已确认的计划结果”转成订单与 `target_book_v1`。
- 保持现有正式 sizing、成交时点、现金约束和基线回测结果不漂移。
- 让正式审计可以明确区分“候选规划层”和“纯执行内核层”。

**Non-Goals**

- 不修改个股或 ETF 的策略语义。
- 不修改市场状态、组合总控、预算口径或资产池。
- 不移除旧的 `build_rebalance_orders()`，只把 stage 主路径从它的候选规划兼容接口中脱离。
- 不在本次变更中重写整个执行引擎。

## Decisions

### 决策 1：`order_planning` 不再回退构建上游合同

采用方案：

- `bridge_adapter.ensure_day()` 继续作为正式上游接线点，负责保证 `candidate_boundary` 与 `candidate_plan` 已存在。
- `order_planning` 若发现缺少这两层正式产物，则直接报错，而不是静默回退构建。

不采用的方案：

- 保留回退构建作为“更稳健”的容错。
  原因：这会让阶段边界继续失真，也会掩盖上游接线错误。

### 决策 2：新增纯执行级订单构建辅助函数

采用方案：

- 在组合执行模块中新增一条纯执行辅助路径，只接收：
  - 已确认的买入计划项
  - 已确认的轮换卖出计划项
  - 当前持仓、现金、开盘价、整手、持仓名额等执行级参数
- 该路径不再接收 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*` 等候选规划参数。

不采用的方案：

- 继续复用 `build_rebalance_orders()` 并传入被固定化的兼容参数。
  原因：这样只是把兼容逻辑藏起来，没有真正把执行内核和候选规划解耦。

### 决策 3：保留旧入口，新增 stage 主路径专用执行入口

采用方案：

- `build_rebalance_orders()` 保留给历史调用方和现有非 stage 单测。
- stage pipeline 改为调用新的纯执行函数。

不采用的方案：

- 直接把 `build_rebalance_orders()` 重构成新接口并同时迁移所有调用方。
  原因：范围过大，不符合这次最小改动原则。

### 决策 4：正式审计新增纯执行层摘要，但不提升研究诊断字段

采用方案：

- 正式审计继续以 `candidate_boundary -> candidate_plan -> execution_kernel` 三层归因来记录拒绝来源。
- 只新增最小正式摘要，不把候选规划或执行排障细节提升成正式运行合同。

不采用的方案：

- 直接把更多 debug 字段写入正式产物。
  原因：这会再次把研究诊断污染到正式执行链。

## Risks / Trade-offs

- [风险] `order_planning` 不再回退后，会更早暴露上游接线遗漏。  
  [缓解] 用明确异常替代静默兜底，并补覆盖该行为的单测。

- [风险] 纯执行辅助函数若与旧入口逻辑不一致，可能导致下单结果漂移。  
  [缓解] 以基线重跑为强约束，逐项对比绩效、交易数和预热起点。

- [风险] 保留旧 `build_rebalance_orders()` 会短期形成“双路径”。  
  [缓解] 明确只有 stage 主路径使用新入口，旧入口仅作兼容保留。
