## ADDED Requirements

### Requirement: 执行内核必须只消费候选规划结果与统一目标持仓
系统 MUST 让 `order_planning` 和后续执行内核只消费 `candidate_plan_v1`、执行级 sizing 必需参数和 `target_book_v1`。执行内核 SHALL NOT 再直接读取 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*` 或等价候选规划兼容配置。

#### Scenario: 执行内核构建订单
- **WHEN** `order_planning` 为某个交易日构建订单
- **THEN** 它 MUST 基于 `candidate_plan_v1` 中的最终候选计划工作
- **THEN** 它 SHALL NOT 再直接根据候选规划兼容配置决定候选保留或替换

#### Scenario: 统一目标持仓继续作为执行真相
- **WHEN** 执行内核完成订单构建
- **THEN** 最终正式执行真相 MUST 继续收敛到 `target_book_v1`
- **THEN** 引入 `candidate_plan_v1` SHALL NOT 替代统一目标持仓合同
