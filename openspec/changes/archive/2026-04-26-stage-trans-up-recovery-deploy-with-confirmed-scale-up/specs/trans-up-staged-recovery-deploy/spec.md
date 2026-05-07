## ADDED Requirements

### Requirement: TRANS_UP 恢复态轻仓部署

系统 MUST 支持在 `TRANS_UP + benchmark_regime_off` 的恢复态放行路径上，对股票 alpha sleeve 的新买入信号施加独立的轻仓缩放，而不是默认按常态部署。

#### Scenario: 恢复态放行时应用轻仓缩放
- **WHEN** `market_state == TRANS_UP`
- **AND** `trade_mode == TREND_LIGHT`
- **AND** `benchmark_regime_on == false`
- **AND** `allow_trans_up_recovery_entries_when_benchmark_off == true`
- **AND** `trans_up_recovery_entry_scale_when_benchmark_off < 1.0`
- **THEN** 系统 MUST 保留恢复态买入信号
- **AND** MUST 将该批买入信号的 `meta.order_value_scale` 乘以 `trans_up_recovery_entry_scale_when_benchmark_off`

#### Scenario: 非恢复态不应用轻仓缩放
- **WHEN** `benchmark_regime_on == true` 或 `market_state != TRANS_UP`
- **THEN** 系统 SHALL NOT 应用 `trans_up_recovery_entry_scale_when_benchmark_off`

### Requirement: 恢复态 staged deploy 可观测

系统 MUST 在日级 diagnostics 中明确写出恢复态轻仓部署是否生效以及应用的缩放值。

#### Scenario: 恢复态 staged deploy 被激活
- **WHEN** 当日 `TRANS_UP` 恢复态放行路径被启用
- **THEN** diagnostics MUST 输出：
  - `trans_up_recovery_gate_relaxed`
  - `trans_up_recovery_entry_scale_applied`
  - `trans_up_recovery_scaled_entry_count`
