## ADDED Requirements

### Requirement: 系统架构文档必须把候选边界层写成正式共享主链的一部分
系统架构文档 MUST 明确写出“子系统 -> 候选边界层 -> 执行内核 -> 正式审计”的正式共享主链，并说明候选边界层负责子系统名额、兼容裁决和最终候选集合确认。文档 SHALL NOT 再把这些职责归到 `order_planning`。

#### Scenario: 阅读全系统架构设计文档
- **WHEN** 维护者阅读正式系统架构设计文档
- **THEN** 文档 MUST 明确候选边界层位于子系统与执行内核之间
- **THEN** 文档 MUST 说明 `order_planning` 仅负责订单规划和执行级 sizing
