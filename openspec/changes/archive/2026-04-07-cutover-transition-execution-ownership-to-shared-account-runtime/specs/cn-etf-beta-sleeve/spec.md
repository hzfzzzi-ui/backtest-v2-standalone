## ADDED Requirements

### Requirement: ETF beta sleeve 在账户层主真相下只能作为 transition execution adapter
当 `runtime_truth_source = account_allocator` 时，ETF beta sleeve MUST 作为共享账户执行 runtime 的资产执行 adapter。旧 weak-state 路径可以继续产出研究与排障信息，但 SHALL NOT 再作为账户层 transition execution 的主 owner。

#### Scenario: 账户层 owner 存在时旧 weak-state 路径降级
- **WHEN** 账户层共享执行 runtime 已输出 transition execution owner
- **THEN** `state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`weak_state_inter_rebalance_defense_redeploy` 只允许写入 diagnostics/reference
- **THEN** ETF beta sleeve SHALL NOT 再用这些旧路径输出主执行结论或主 reject reason
