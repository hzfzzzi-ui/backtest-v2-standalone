## ADDED Requirements

### Requirement: 个股子系统必须在进入执行内核前形成候选规划真相
`cn_stock_trend_alpha_core` MUST 在进入执行内核前形成自己的候选规划真相，包括现金感知候选选择、轮换替换和候选排序后的最终保留集合。该子系统 SHALL NOT 把这些候选规划兼容语义留给共享执行内核临时决定。

#### Scenario: 现金感知候选选择启用
- **WHEN** 个股子系统启用现金感知候选选择
- **THEN** 子系统 MUST 在进入执行内核前完成最终候选集合决策
- **THEN** 执行内核 SHALL 只接收规划结果

#### Scenario: 轮换替换启用
- **WHEN** 个股子系统启用轮换替换
- **THEN** 子系统 MUST 在候选规划阶段形成替换对与保留候选结果
- **THEN** 执行内核 SHALL NOT 再自行决定是否执行候选替换
