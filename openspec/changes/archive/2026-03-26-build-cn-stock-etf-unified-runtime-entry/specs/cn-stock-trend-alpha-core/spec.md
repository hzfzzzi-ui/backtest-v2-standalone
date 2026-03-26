## ADDED Requirements

### Requirement: 股票 alpha sleeve 必须支持在 unified runtime 中作为组合子腿运行
`cn_stock_trend_alpha_core` MUST 支持在同一次 unified runtime 实验中作为组合子腿运行，并继续保留自身的股票资产读表、候选生成、排序和本地风控语义。该 sleeve SHALL NOT 因 unified runtime 引入而被迫改写成 ETF 或多资产混合 provider。

#### Scenario: 股票 alpha sleeve 在统一实验中运行
- **WHEN** 统一运行实验启用 `cn_stock_trend_alpha_core`
- **THEN** 股票 alpha sleeve MUST 继续消费 `cn_a_equity` 数据链和股票专属配置
- **THEN** 其输出 MUST 以 sleeve 级结果形式进入组合汇总

#### Scenario: 股票 alpha sleeve 不再独占整次实验
- **WHEN** 股票 alpha sleeve 与 ETF beta sleeve 并行运行
- **THEN** 股票 alpha sleeve SHALL NOT 再被视为整次实验唯一资产真相
- **THEN** 其产物 MUST 明确属于组合内的一个 sleeve
