## MODIFIED Requirements

### Requirement: 执行内核必须只消费候选规划结果与统一目标持仓
系统 MUST 让 `order_planning` 及其后续正式执行链只消费上游已确认的 `candidate_plan_v1`、执行级必要参数和 `target_book_v1`。执行内核 SHALL NOT 再直接依赖候选规划兼容配置来决定买入计划。

#### Scenario: stage 主路径构建订单
- **WHEN** `order_planning` 在 stage pipeline 中为某个交易日构建订单
- **THEN** 它 MUST 从上游读取已存在的 `candidate_plan_v1`
- **THEN** 它 SHALL NOT 再直接读取 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*` 等候选规划兼容配置

#### Scenario: 上游正式产物缺失
- **WHEN** `order_planning` 进入执行阶段时缺少 `candidate_boundary_v1` 或 `candidate_plan_v1`
- **THEN** 系统 MUST 报告明确的运行时错误
- **THEN** 系统 SHALL NOT 在 `order_planning` 内部静默回退重建这些上游合同

### Requirement: stage 主路径必须通过纯执行入口构建订单
系统 MUST 为 stage pipeline 提供纯执行级订单构建入口，使共享执行层只处理卖出合并、现金约束、整手约束、持仓名额和统一目标持仓映射，而不再承担候选规划解释职责。

#### Scenario: stage 主路径调用下单辅助函数
- **WHEN** stage pipeline 需要把已确认的计划结果转成订单
- **THEN** 系统 MUST 调用纯执行级入口
- **THEN** 该入口 MUST 只接收已确认的计划项和执行级必要参数

#### Scenario: 旧兼容入口仍被历史路径使用
- **WHEN** 非 stage 历史调用方继续使用旧的 `build_rebalance_orders()`
- **THEN** 系统 MAY 继续保留该入口
- **THEN** 该兼容入口 SHALL NOT 阻止 stage 主路径迁移到纯执行入口
