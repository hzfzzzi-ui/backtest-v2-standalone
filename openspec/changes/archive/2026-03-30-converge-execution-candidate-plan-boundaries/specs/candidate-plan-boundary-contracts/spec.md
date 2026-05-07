## ADDED Requirements

### Requirement: 系统必须提供候选规划正式合同
系统 MUST 在 `candidate_boundary_v1` 与执行内核之间提供 `candidate_plan_v1` 正式合同。该合同 MUST 表达候选边界确认后的最终候选计划、轮换替换结果、现金感知选择结果和规划层拒绝摘要。

#### Scenario: 个股子系统生成候选规划合同
- **WHEN** A股个股子系统完成候选边界确认并准备进入执行内核
- **THEN** 系统 MUST 生成 `candidate_plan_v1`
- **THEN** 该 payload MUST 至少包含最终买入候选顺序、规划层拒绝原因计数和轮换替换摘要

#### Scenario: ETF 子系统直通候选规划合同
- **WHEN** ETF 子系统当前无需现金感知搜索或轮换替换
- **THEN** 系统 MUST 仍生成合法的 `candidate_plan_v1`
- **THEN** 该 payload MAY 为最小直通规划结果，但 SHALL 保持统一合同结构

### Requirement: 候选规划合同必须先于执行内核收敛候选兼容语义
系统 MUST 在进入执行内核前，先于 `order_planning` 收敛 `candidate_plan_mode`、现金感知搜索和轮换替换等候选规划兼容语义。执行内核 SHALL NOT 直接基于这些配置字段重新推导候选计划。

#### Scenario: 候选规划模式启用
- **WHEN** 运行时启用了现金感知搜索或轮换替换
- **THEN** 这些兼容语义 MUST 在 `candidate_plan_v1` 生成阶段完成
- **THEN** 执行内核 SHALL 只消费规划结果而不是原始模式配置
