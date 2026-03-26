## ADDED Requirements

### Requirement: Governor 必须支持 ETF 槽位化目标暴露审计
当 A 股系统运行 A0 V2 研究模板时，Governor MUST 能暴露 ETF sleeve 的槽位化目标暴露摘要，包括：
- `core_slot_target_exposure`
- `growth_slot_target_exposure`
- `core_slot_actual_exposure`
- `growth_slot_actual_exposure`
- `slot_under_deploy_reason_codes`

#### Scenario: Governor 可解释 ETF 槽位为什么没开满
- **WHEN** A0 V2 的 ETF sleeve 未达到目标暴露
- **THEN** Governor 摘要 MUST 能回答是核心槽位、成长槽位还是两者共同导致未部署
