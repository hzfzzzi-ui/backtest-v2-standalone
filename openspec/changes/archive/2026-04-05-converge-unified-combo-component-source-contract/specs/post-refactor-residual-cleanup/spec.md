## ADDED Requirements

### Requirement: cleanup MUST preserve validated replay anchors before removing unified combo transitional provenance
在删除 unified combo 的 transitional provenance 之前，系统 MUST 先复现已验证的 replay anchor。当前有效锚点是 `A_STOCK_ETF_V1` 对应的目标语义：目标实验 `exp_20260404_074403089_e18e`，并由 2026-04-04 的后端 `exp_20260404_091050531_532d` 与前端 `exp_20260404_092114076_8491` 复跑结果共同验证。

#### Scenario: 清理 `research_custom_sleeves` 前的 gate 审计
- **WHEN** 系统准备移除 `research_custom_sleeves` 或等效 transitional provenance
- **THEN** 替代路径 MUST 先复现上述 replay anchor 的绩效语义与组件来源语义
- **THEN** cleanup SHALL NOT 仅因存在更正式的设计稿就提前删除仍承担回放职责的过渡链路
