## ADDED Requirements

### Requirement: Defense establish research tuning variants
系统 SHALL 为共享账户 `defense establish` 提供正式研究变体，至少覆盖触发边界和已持仓 top-up 两个维度。

#### Scenario: runtime 选择研究变体
- **WHEN** 共享账户 transition policy 编译运行时研究配置
- **THEN** 系统 MUST 输出当前生效的 `variant_id`
- **AND** 系统 MUST 输出该变体的 `edge_to_states`
- **AND** 系统 MUST 输出该变体是否允许 `top_up_existing_defense`
