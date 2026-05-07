## ADDED Requirements

### Requirement: ETF beta sleeve 在 `RISK_OFF` 下必须允许现金驱动的小额补仓
当 ETF beta sleeve 运行于 `RISK_OFF`，且正式弱势目标存在未完成缺口时，系统 MUST 支持基于可用现金的 inter-rebalance 小额补仓。该路径 SHALL 保持债优先、核心宽基次之，并 SHALL NOT 改写 `TRANS_DOWN / BULL / TRANS_UP` 的执行行为。

#### Scenario: `RISK_OFF` 下只要有现金就允许小额补仓
- **WHEN** ETF beta sleeve 运行于 `RISK_OFF`
- **AND** 当前 live exposure 低于正式目标
- **AND** 有可用现金满足最小可执行单位
- **THEN** 系统 MUST 允许一次债优先的小额补仓
- **THEN** 系统 SHALL NOT 要求先满足完整 deploy gap
