## ADDED Requirements

### Requirement: TRANS_UP 恢复态旁路必须支持独立质量过滤
系统 MUST 支持一个仅作用于 `TRANS_UP + benchmark_off` 恢复态旁路的可选质量过滤。该过滤 SHALL 只复用现有 `residual_strength_score` 与 `breakout_margin_score`，且 SHALL 只作用于 `alpha_source = breakout / pullback_overlap`。

#### Scenario: 关闭时保持现状
- **WHEN** `trans_up_recovery_quality_filter_enabled = false` 或未配置
- **THEN** 恢复态旁路 SHALL 与当前放松 benchmark gate 的行为保持一致

#### Scenario: 低 residual_strength_score 时阻断恢复态 entry
- **WHEN** `trans_up_recovery_quality_filter_enabled = true`
- **AND** `market_state = TRANS_UP`
- **AND** `trade_mode = TREND_LIGHT`
- **AND** `benchmark_regime_on = false`
- **AND** 候选 `alpha_source` 属于 `breakout / pullback_overlap`
- **AND** `residual_strength_score < trans_up_recovery_min_residual_strength_score`
- **THEN** 该候选 SHALL 被阻断

#### Scenario: 低 breakout_margin_score 时阻断恢复态 entry
- **WHEN** `trans_up_recovery_quality_filter_enabled = true`
- **AND** `market_state = TRANS_UP`
- **AND** `trade_mode = TREND_LIGHT`
- **AND** `benchmark_regime_on = false`
- **AND** 候选 `alpha_source` 属于 `breakout / pullback_overlap`
- **AND** `breakout_margin_score < trans_up_recovery_min_breakout_margin_score`
- **THEN** 该候选 SHALL 被阻断

#### Scenario: 不影响 pullback_only
- **WHEN** 候选 `alpha_source = pullback_only`
- **THEN** 恢复态质量过滤 SHALL 不阻断该候选

### Requirement: 恢复态质量过滤必须可观测
系统 MUST 为恢复态质量过滤输出独立 diagnostics，便于研究归因。

#### Scenario: diagnostics 记录恢复态质量过滤
- **WHEN** 恢复态质量过滤已启用并发生阻断
- **THEN** `diagnostics` MUST 记录 `trans_up_recovery_quality_filter_applied = true`
- **THEN** `diagnostics` MUST 记录总阻断数
- **THEN** `diagnostics` MUST 分别记录 residual 与 breakout margin 两类阻断数
