## ADDED Requirements

### Requirement: 个股子系统必须在进入执行内核前完成候选兼容裁决
`cn_stock_trend_alpha_core` 在多信号组合路径下 MUST 将同股兼容裁决、市场状态权重覆写、子系统名额分配和最终候选截断视为子系统上游候选边界的一部分。该边界结果 MUST 在进入执行内核前固定下来，执行内核 SHALL NOT 再重建这些裁决。

#### Scenario: 多信号个股路径进入执行内核
- **WHEN** 个股多信号路径已经形成当日组合后候选
- **THEN** 系统 MUST 在进入执行内核前完成子系统名额和兼容裁决
- **THEN** 执行内核 SHALL 只接收裁决后的最终候选集合
