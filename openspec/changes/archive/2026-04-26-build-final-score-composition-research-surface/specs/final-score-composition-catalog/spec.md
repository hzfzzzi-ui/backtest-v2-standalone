## ADDED Requirements

### Requirement: Final Score Composition Catalog
系统 MUST 提供 `RESEARCH_ONLY` 的 final score composition catalog，定义主线 `_final_score` 的原子组成项、组合分与解释边界。

#### Scenario: Catalog exposes canonical final score components
- **WHEN** 研究层请求 final score composition catalog
- **THEN** catalog MUST 返回 canonical 组成项定义
- **AND** 每个组成项 MUST 包含名称、说明、方向约定、as-of 约束和是否直接参与 `_final_score`
- **AND** catalog MUST 明确 `_final_score` 总分与原子组成项的关系
