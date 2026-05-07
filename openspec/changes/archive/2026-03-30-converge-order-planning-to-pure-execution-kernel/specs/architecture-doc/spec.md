## MODIFIED Requirements

### Requirement: 架构文档必须把 order_planning 锚定为纯执行内核
系统架构文档 MUST 明确 `order_planning` 属于共享执行内核，而不是候选规划兼容层。文档 MUST 表述为：候选边界和候选规划在进入 `order_planning` 之前已经完成，`order_planning` 只负责执行级转换。

#### Scenario: 维护者阅读执行链路
- **WHEN** 维护者阅读全系统架构设计中的执行链路说明
- **THEN** 文档 MUST 明确列出 `candidate_boundary_v1 -> candidate_plan_v1 -> order_planning -> target_book_v1`
- **THEN** 文档 SHALL NOT 把 `order_planning` 描述为继续解释候选规划参数的兼容层
