## ADDED Requirements

### Requirement: 主系统必须在订单规划前提供候选边界合同
系统 MUST 在共享执行进入 `order_planning` 之前生成 `candidate_boundary_v1` 合同，用于表达当日已经完成子系统名额、兼容裁决和候选截断后的正式买入候选集合。该合同 MUST 早于订单规划生成，且 SHALL NOT 与最终目标持仓单混为同一真相。

#### Scenario: 多信号个股路径进入订单规划前生成候选边界
- **WHEN** A股个股多信号路径在当日已经得到 `day_signals`、`controls` 和卖出后的持仓占用
- **THEN** 系统 MUST 先生成 `candidate_boundary_v1`
- **THEN** `order_planning` MUST 消费该合同中的最终候选集合，而不是重新解析子系统权重和名额

### Requirement: 候选边界合同必须记录最小可审计裁决摘要
`candidate_boundary_v1` MUST 至少记录 `decision_date`、`boundary_mode`、`selected_buy_symbols`、`owner_system_counts`、`slot_caps`、`available_slots`、`reject_reason_counts` 和最小诊断摘要。该合同 SHALL 只回答“哪些候选被允许进入订单规划”，而 SHALL NOT 直接承载订单或成交结果。

#### Scenario: 读取候选边界摘要
- **WHEN** 研究诊断或日级审计读取当日候选边界结果
- **THEN** 系统 MUST 返回候选边界的已选候选、名额摘要和拒绝原因摘要
- **THEN** 返回结果 SHALL NOT 伪装成最终目标持仓或正式订单真相
