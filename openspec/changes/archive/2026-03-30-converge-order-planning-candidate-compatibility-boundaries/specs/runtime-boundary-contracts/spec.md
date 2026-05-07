## ADDED Requirements

### Requirement: 订单规划必须只消费上游候选边界结果和统一目标持仓单
共享执行中的 `order_planning` MUST 只消费上游候选边界层已经确认的买入候选集合，以及后续统一目标持仓单所需的执行输入。`order_planning` SHALL NOT 再直接读取 `signal_composition`、`market_state_weight_overrides` 或子系统名额裁决配置来重建候选边界。

#### Scenario: 构建当日订单规划
- **WHEN** `order_planning` 为当日构建订单
- **THEN** 它 MUST 使用候选边界层输出的最终买入候选集合
- **THEN** 它 SHALL NOT 在执行内核中再次解析子系统权重、状态覆写和候选截断逻辑

### Requirement: 执行级 sizing 必须与候选边界裁决分层
共享执行中的现金约束、最小交易单位、轮换替换和 `candidate_plan_mode` 等执行级 sizing 逻辑 MUST 保留在执行内核；它们 MUST 建立在候选边界层已确认的候选集合之上，而不是反向承担子系统兼容裁决。

#### Scenario: 现金感知搜索启用
- **WHEN** 执行内核启用 `cash_aware` 或其他执行级 sizing 逻辑
- **THEN** 它 MUST 只在候选边界层已经确认的候选集合内做订单可行性搜索
- **THEN** 它 SHALL NOT 把执行级搜索结果写回为新的子系统候选真相
