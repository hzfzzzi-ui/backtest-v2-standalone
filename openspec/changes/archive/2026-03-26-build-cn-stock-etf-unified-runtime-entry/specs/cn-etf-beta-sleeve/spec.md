## ADDED Requirements

### Requirement: ETF beta sleeve 必须支持在 unified runtime 中与股票 alpha 并行运行
`cn_etf_beta` MUST 支持在同一次 unified runtime 实验中与 `cn_stock_trend_alpha_core` 并行运行，而不是仅在全局 `asset_scope=cn_etf` 时独占实验。ETF beta sleeve MUST 继续使用其 ETF provider、ETF 候选池与 ETF 读表语义。

#### Scenario: ETF beta sleeve 在统一实验中运行
- **WHEN** 统一运行实验启用 `cn_etf_beta`
- **THEN** ETF beta sleeve MUST 继续消费 `cn_etf` 数据链和 ETF selector/provider
- **THEN** 其输出 MUST 以 sleeve 级结果形式进入组合汇总

#### Scenario: ETF beta sleeve 不再要求独占 asset_scope
- **WHEN** 统一运行实验包含股票 alpha sleeve
- **THEN** ETF beta sleeve SHALL NOT 因全局 `asset_scope` 不是 `cn_etf` 而被静默禁用
- **THEN** 系统 MUST 明确暴露其部署状态与未部署原因
