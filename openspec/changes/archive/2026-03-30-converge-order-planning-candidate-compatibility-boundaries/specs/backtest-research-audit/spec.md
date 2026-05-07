## ADDED Requirements

### Requirement: 研究诊断必须把候选边界裁决与执行规划分开归因
研究诊断与日级审计 MUST 将子系统名额不足、候选兼容冲突、状态权重覆写导致的候选截断归因到“候选边界层”，而不是继续归因到执行内核的订单规划阶段。

#### Scenario: 记录候选边界拒绝原因
- **WHEN** 当日存在 `SLEEVE_BUDGET_EXCEEDED` 或其他候选边界拒绝
- **THEN** 研究诊断 MUST 将该拒绝记录在候选边界归因层
- **THEN** 正式或研究产物 SHALL NOT 把该拒绝误标为执行内核 sizing 拒绝
