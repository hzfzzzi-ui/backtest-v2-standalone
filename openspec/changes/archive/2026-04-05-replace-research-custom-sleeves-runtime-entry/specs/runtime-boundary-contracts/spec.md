## ADDED Requirements

### Requirement: unified combo component source contract MUST become the primary runtime source boundary before legacy sleeves are retired
系统在 unified combo 研究链路中 MUST 先把 `component_source_contract` 提升为主运行来源边界，再考虑删除 legacy `sleeves` 与 `research_custom_sleeves` 入口。legacy `sleeves` 当前 SHALL 只作为 fallback。

#### Scenario: unified combo 运行时同时存在 contract 与 legacy sleeves
- **WHEN** unified combo payload 同时包含 `component_source_contract` 与 `unified_runtime.sleeves`
- **THEN** 系统 MUST 先消费 `component_source_contract`
- **THEN** `unified_runtime.sleeves` SHALL 仅在 contract 缺失或不完整时才生效
