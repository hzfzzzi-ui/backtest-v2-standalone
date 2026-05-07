## ADDED Requirements

### Requirement: 系统架构文档必须显式包含候选规划层
系统架构文档 MUST 在当前正式运行链中显式表达候选规划层位于 `candidate_boundary_v1` 与执行内核之间，并说明其负责候选排序收敛、现金感知选择和轮换替换等兼容规划语义。

#### Scenario: 阅读阶段流水线架构图
- **WHEN** 维护者阅读正式系统架构设计文档
- **THEN** 文档 MUST 能明确看到候选规划层的正式位置
- **THEN** 文档 SHALL NOT 继续把这些兼容规划语义描述为执行内核内部职责
