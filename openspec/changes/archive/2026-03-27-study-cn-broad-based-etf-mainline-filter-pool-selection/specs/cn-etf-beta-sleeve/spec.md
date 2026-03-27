## ADDED Requirements

### Requirement: 宽基ETF主线必须显式支持绝对过滤 profile
当 `cn_etf_beta` 以宽基 ETF 独立主线运行时，系统 MUST 显式暴露 `absolute_filter_profile`，并将绝对过滤拒绝统计、拒绝 reason codes 和过滤后剩余可选资产数量写入正式产物。

#### Scenario: 绝对过滤 profile 可被审计
- **WHEN** 用户切换宽基 ETF 主线的 `absolute_filter_profile`
- **THEN** 系统 MUST 在 `run_meta`、`audit` 或等价产物中显式记录当前 profile
- **THEN** 系统 MUST 输出该 profile 导致的拒绝天数、拒绝 reason codes 和过滤后合格候选数统计

### Requirement: 宽基ETF主线必须显式支持候选池 profile
当 `cn_etf_beta` 以宽基 ETF 独立主线运行时，系统 MUST 显式暴露 `candidate_pool_profile`，并能回答每个交易日哪些 ETF 因 pool profile 进入候选池、哪些 ETF 因 pool profile 被排除。

#### Scenario: 候选池 profile 可被审计
- **WHEN** 用户切换宽基 ETF 主线的 `candidate_pool_profile`
- **THEN** 系统 MUST 输出当前候选池 profile 标识
- **THEN** 系统 MUST 输出候选池覆盖摘要和入池/出池原因，而不是只给最终持仓结果

### Requirement: 宽基ETF主线必须显式支持选择链路 profile
当 `cn_etf_beta` 以宽基 ETF 独立主线运行时，系统 MUST 显式暴露 `selection_chain_profile`，并能回答最终持仓是如何从候选池中胜出，以及未入选 ETF 是在排序、槽位还是 deployability 环节被淘汰。

#### Scenario: 选择链路 profile 可被审计
- **WHEN** 用户切换宽基 ETF 主线的 `selection_chain_profile`
- **THEN** 系统 MUST 输出最终 winner 统计
- **THEN** 系统 MUST 输出 selection reject 的 reason codes，而不是只输出 `selected_etfs`
