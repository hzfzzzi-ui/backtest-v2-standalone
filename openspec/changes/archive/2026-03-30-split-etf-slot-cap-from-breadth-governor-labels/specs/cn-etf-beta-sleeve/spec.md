## ADDED Requirements

### Requirement: ETF beta sleeve 必须输出可供 Governor 消费的 slot-cap 来源
当 `cn_etf_beta` sleeve 计算正式 Phase 1 的 `target_selected_count` 与 `slot_cap` 时，系统 MUST 输出稳定的 slot-cap 来源字段，并允许 Governor 直接消费该字段来构造预算归因标签。

#### Scenario: provider 向下游暴露 slot-cap 来源
- **WHEN** ETF beta sleeve 完成某交易日的 Phase 1 预算与目标计算
- **THEN** 系统 MUST 暴露该日 `target_selected_count_source` 或等价来源字段
- **THEN** 该来源字段 MUST 与最终写入 Governor 快照的 slot-cap 来源保持一致

### Requirement: ETF beta sleeve 的 zero-slot 归因不得伪装成 breadth
当 `cn_etf_beta` sleeve 因本地 slot-cap 或目标数归零而无法部署时，系统 MUST 将该事实作为 ETF sleeve 约束暴露给下游，而 SHALL NOT 让下游把该约束解释成 breadth 信号。

#### Scenario: zero-slot 日仍保持 ETF 语义
- **WHEN** 某个正式 ETF 交易日 `slot_cap <= 0`
- **THEN** ETF diagnostics MUST 保留 ETF sleeve 自身的 slot-cap 原因
- **THEN** Governor 和 rootcause 摘要 MUST 能把它识别为 ETF sleeve 约束而不是 breadth 约束
