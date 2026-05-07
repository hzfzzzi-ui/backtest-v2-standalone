## ADDED Requirements

### Requirement: stage-pipeline fill accounting 必须正式消费 slippage_mode
系统 SHALL 在当前正式 stage-pipeline fill 路径中正式消费 `costs.slippage_mode`。

#### Scenario: `price_adjustment_only` 通过 fill price 偏移体现 slippage
- **WHEN** `costs.slippage_mode = "price_adjustment_only"`
- **THEN** fill accounting MUST 通过偏移 `fill_price` 体现 slippage，并保持现有净额方向

#### Scenario: `cost_only` 不改 fill price
- **WHEN** `costs.slippage_mode = "cost_only"`
- **THEN** fill accounting MUST 保持 `fill_price == open`，并将 slippage 作为独立现金成本计入净额

#### Scenario: 默认模式保持兼容
- **WHEN** 未显式声明 `slippage_mode`
- **THEN** 系统 MUST 继续按 `price_adjustment_only` 解释
