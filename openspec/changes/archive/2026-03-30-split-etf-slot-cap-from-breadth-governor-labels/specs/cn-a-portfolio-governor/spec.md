## ADDED Requirements

### Requirement: Governor 必须区分真实 breadth 限仓与 ETF sleeve slot-cap 限仓
当 `global_portfolio_governor` 为 `cn_etf` 输出预算证据链时，系统 MUST 区分真实 breadth 模块施加的仓位压缩和 ETF sleeve 本地 slot-cap 施加的仓位压缩。Governor SHALL NOT 再把 ETF sleeve 的 slot-cap 压缩误报为 `BREADTH_CAP_ACTIVE`。

#### Scenario: breadth 未启用时不得误报 breadth 标签
- **WHEN** `cn_etf` 运行中 breadth 模块未启用，但 ETF sleeve slot-cap 小于 `hard_max_positions`
- **THEN** Governor MUST NOT 输出 `BREADTH_CAP_ACTIVE`
- **THEN** Governor MUST 输出独立的 ETF slot-cap 标签或等价字段

#### Scenario: breadth 与 ETF slot-cap 同时生效时可同时归因
- **WHEN** breadth 模块真实压缩仓位，且 ETF sleeve slot-cap 也进一步压缩预算
- **THEN** Governor MUST 同时保留 breadth 和 ETF slot-cap 两类归因
- **THEN** 预算证据链 MUST 能让下游审计区分两者不是同一个原因

### Requirement: Governor 必须暴露 slot-cap 最小来源字段
当 `cn_etf` sleeve 的预算被 slot-cap 压缩时，Governor MUST 在预算快照中暴露最小可审计的 slot-cap 来源字段，供 diagnostics、audit 和 rootcause 摘要直接消费，而 SHALL NOT 要求下游根据 runtime reason codes 反推来源。

#### Scenario: ETF slot-cap 来源可被快照直接读取
- **WHEN** Governor 输出某个 `cn_etf` 交易日预算摘要
- **THEN** 快照 MUST 直接包含 slot-cap 是否生效以及其来源文本
- **THEN** 下游系统 MUST 能仅依赖 Governor 快照判断该日是否属于 ETF slot-cap 压缩
