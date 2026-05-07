## ADDED Requirements

### Requirement: 日级信号协议必须保留候选边界所需的最小元信息
`DaySignals` 中进入候选边界层的买入候选 MUST 保留进行上游边界裁决所需的最小元信息，包括 `owner_system`、`sleeve_id`、排序分数和正式原因摘要。信号协议 SHALL 允许上游候选边界层消费这些信息，但 SHALL NOT 要求执行内核直接理解它们的子系统语义。

#### Scenario: 个股多信号路径产出候选信号
- **WHEN** 个股多信号路径返回 `DaySignals.buy_signals`
- **THEN** 每条候选信号 MUST 带有候选边界层所需的最小元信息
- **THEN** 这些元信息 MUST 足以支持上游候选边界层完成名额和兼容裁决

#### Scenario: 执行内核消费最终候选
- **WHEN** 共享执行开始订单规划
- **THEN** 执行内核 MAY 读取统一后的正式原因摘要
- **THEN** 执行内核 SHALL NOT 直接依赖子系统私有兼容裁决配置
