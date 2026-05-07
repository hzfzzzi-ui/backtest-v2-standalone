## ADDED Requirements

### Requirement: ETF partial fallback fill 不得把零原始目标的 fallback 标的压成正 `target_weight`

当 ETF standalone research mainline 在 partial fallback fill 场景下追加 fallback 标的时，系统 MUST 保持原始正目标权重标的的 live target 语义。若选中集合中仍存在原始正目标权重标的，则零原始目标的 fallback 标的 SHALL NOT 获得正的 `target_weight`。

#### Scenario: partial fill 只压缩原始正目标标的

- **WHEN** ETF standalone research mainline 的选中集合同时包含原始正目标标的与零原始目标 fallback 标的
- **THEN** 系统 MUST 仅在原始正目标标的之间按比例压缩 `live_target`
- **THEN** fallback 标的的 `target_weight` MUST 保持为 `0.0`

### Requirement: ETF full fallback replacement 仍可承接 live target

当 ETF standalone research mainline 进入 full fallback replacement，且选中集合中不存在任何原始正目标权重标的时，系统 MUST 继续支持由 fallback 选中集合承接 `live_target` 的既有研究语义。

#### Scenario: full replacement 时 fallback 可承接 live target

- **WHEN** ETF standalone research mainline 的选中集合中不存在任何原始正目标权重标的
- **THEN** 系统 MAY 将 `live_target` 分配给 fallback 选中集合
- **THEN** 该分配 MUST 继续遵守现有 `target_weight <= 1.0` 的执行合同
