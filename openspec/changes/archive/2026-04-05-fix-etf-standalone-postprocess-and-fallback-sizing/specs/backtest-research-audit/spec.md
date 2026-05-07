## MODIFIED Requirements

### Requirement: research audit 必须显式检测 ETF target contract drift
当 formal ETF Phase 1 或 ETF standalone research mainline 在同一决策日的 `orders.csv`、`portfolio_daily.csv`、`rebalance_day_summary.csv` 或等价 artifact 中出现多套最终目标仓位口径时，`research_audit` MUST 将其视为 target contract drift。对于 standalone inter-rebalance deploy，审计 MUST 将 `orders` 中的 delta `target_weight` 与 `final_target_weight` 分开解释；系统 SHALL NOT 因为 delta BUY order 与最终目标仓位天然不同，就误报 target contract drift。

#### Scenario: 同日 final target 口径冲突
- **WHEN** formal ETF Phase 1 或 standalone mainline 的同一决策日在 orders、daily 或 summary 中出现不同的 `final_target_weight` / 最终目标仓位口径
- **THEN** `research_audit` MUST 标记 target contract drift
- **THEN** 审计 MUST 引用冲突的 artifact 路径、字段和值，而不是继续给出表面正常的 ETF target 统计

#### Scenario: standalone delta BUY 不得被误判为 drift
- **WHEN** standalone inter-rebalance deploy 的 `orders` 仅在 delta `target_weight` 上与 daily 或 summary 的最终目标仓位不同，但同日 `final_target_weight` 与正式目标合同一致
- **THEN** `research_audit` SHALL NOT 将该差异标记为 target contract drift
- **THEN** 审计 MUST 将该差异解释为 delta deploy gap，而不是最终目标合同冲突

#### Scenario: 未发现 final target 口径冲突
- **WHEN** formal ETF Phase 1 或 standalone mainline 的各项 ETF artifact 在同一决策日共享一致的唯一最终目标仓位
- **THEN** `research_audit` MAY 将 ETF target contract 判定为通过
- **THEN** 审计结论 MUST 可追溯到对应的 orders、daily 和 summary 证据
