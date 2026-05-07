## ADDED Requirements

### Requirement: research audit 必须以执行级唯一目标仓位统计 formal ETF target
当实验属于 Governed A 股 formal ETF Phase 1 主线时，`research_audit` MUST 以执行层实际消费的唯一 ETF `target_exposure` 统计 `avg_target_exposure`、分布摘要和相关结论。审计 SHALL NOT 再从另一条 Governor 或 runtime budget 链重构出与执行目标不同量纲的 ETF target。

#### Scenario: avg_target_exposure 与执行层目标一致
- **WHEN** formal ETF Phase 1 实验同时产出 orders、daily 和 audit 结果
- **THEN** `research_audit` 中的 ETF `avg_target_exposure` MUST 与执行层 target contract 对齐
- **THEN** 审计 SHALL NOT 使用与 orders 中 BUY signal target 不同量纲的值参与 ETF target 均值统计

#### Scenario: explanatory multiplier 不得进入 avg_target_exposure
- **WHEN** 实验产物中同时存在 ETF notional target 与 upstream risk-budget multiplier 等解释性证据
- **THEN** `research_audit` MUST 仅将 notional target 纳入 `avg_target_exposure`
- **THEN** 解释性 multiplier MUST 作为独立证据展示，而不是被折叠进 ETF target 统计

### Requirement: research audit 必须显式检测 ETF target contract drift
当 formal ETF Phase 1 在同一决策日的 `orders.csv`、`portfolio_daily.csv`、`rebalance_day_summary.csv` 或等价 artifact 中出现多套目标仓位口径时，`research_audit` MUST 将其视为 target contract drift。审计 MUST 输出明确的失败或告警结论，并引用冲突 artifact 作为证据。

#### Scenario: 同日 target 口径冲突
- **WHEN** formal ETF Phase 1 的同一决策日在 orders 与 daily 或 summary 中出现不同量纲的 ETF target
- **THEN** `research_audit` MUST 标记 target contract drift
- **THEN** 审计 MUST 引用冲突的 artifact 路径、字段和值，而不是继续给出表面正常的 ETF target 统计

#### Scenario: 未发现口径冲突
- **WHEN** formal ETF Phase 1 的各项 ETF artifact 在同一决策日共享一致的唯一目标仓位
- **THEN** `research_audit` MAY 将 ETF target contract 判定为通过
- **THEN** 审计结论 MUST 可追溯到对应的 orders、daily 和 summary 证据
