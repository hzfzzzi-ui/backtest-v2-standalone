## ADDED Requirements

### Requirement: domestic-only combo V3 promotion MUST bind the full-period experiment

当用户明确要求将 `DOMESTIC_POOL_BASE` 三窗口审计结果提升为组合基线 V3 时，系统 MUST 将 baseline truth 绑定到全周期 `1226` 组合实验，而不是绑定主窗口或硬门槛窗口实验。

#### Scenario: promote DOMESTIC_POOL_BASE to V3
- **WHEN** 操作方执行组合基线 V3 提升
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` MUST 记录 `linked_exp_id = exp_20260510_034302669_7790`
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` MUST 记录 `execution_contract_ref`
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` MUST 成为 `cn_a_multi_sleeve:2012-2026` 的唯一 active baseline
- **THEN** 被替代的同周期 baseline MUST 显式标记为非 active 状态
