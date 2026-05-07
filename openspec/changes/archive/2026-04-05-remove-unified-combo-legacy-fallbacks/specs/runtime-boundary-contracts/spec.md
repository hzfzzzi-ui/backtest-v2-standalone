## ADDED Requirements

### Requirement: runtime boundary cleanup MUST retire legacy unified combo fallback consumption after contract-only replay is validated
当 `component_source_contract` 已经能够稳定复现 replay anchor 时，系统 MUST 删除 unified combo 主路径中的 legacy fallback consumption。此后 `research_custom_sleeves` 只可作为历史 provenance，不能再充当当前运行边界的一部分。

#### Scenario: contract-only replay 已验证通过
- **WHEN** `A_STOCK_ETF_V1` 在 contract-only 路径下继续复现目标结果
- **THEN** unified combo 主路径 MUST 删除 legacy fallback consumption
- **THEN** `research_custom_sleeves` SHALL 只保留为历史 provenance 字段
