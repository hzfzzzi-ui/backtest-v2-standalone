## ADDED Requirements

### Requirement: 个股 alpha sleeve 在恢复态旁路下必须支持最小质量收口
`cn_stock_trend_alpha_core` 在 `TRANS_UP` 恢复态放松 benchmark gate 后，MUST 支持一个可选的最小质量收口，以避免低质量恢复态 breakout 大量进入仓位。

#### Scenario: 恢复态旁路质量收口只影响恢复态
- **WHEN** 个股 alpha sleeve 运行在 `BULL` 或其他非恢复态
- **THEN** 恢复态质量收口 SHALL 不改变既有 entry 行为

#### Scenario: 恢复态旁路质量收口不改变股票池
- **WHEN** 启用恢复态质量收口
- **THEN** 股票池、breakout 主逻辑、`pullback_only` 行为 SHALL 保持不变
