## MODIFIED Requirements

### Requirement: 架构文档必须把 sizing 真相描述为单一路径
系统架构文档 MUST 明确描述正式执行链的 sizing 真相只存在于共享执行路径中，而不是分散在候选规划、执行订单和兼容入口三处。

#### Scenario: 维护者阅读执行链文档
- **WHEN** 维护者阅读全系统架构设计中的执行链说明
- **THEN** 文档 MUST 将 `build_rebalance_orders()` 描述为兼容编排层
- **THEN** 文档 MUST 明确正式 sizing 真相由共享执行路径提供
