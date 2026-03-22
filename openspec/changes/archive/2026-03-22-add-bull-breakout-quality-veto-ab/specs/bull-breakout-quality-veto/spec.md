## ADDED Requirements

### Requirement: BULL breakout quality veto

系统 SHALL 支持一个可选的 `bull_breakout_quality_veto`，仅在 `BULL / TREND_MAIN` 语义下对 breakout 新买入候选执行低自由度、可解释的坏 breakout 阻断。

首轮 veto 只允许使用以下两个现有特征：

- `residual_strength_score`
- `breakout_margin_score`

且只作用于：

- `alpha_source = breakout`
- `alpha_source = pullback_overlap`

#### Scenario: veto 关闭时行为不变
- **WHEN** `bull_breakout_quality_veto_enabled = false` 或未配置
- **THEN** breakout provider 的买入候选行为 SHALL 与变更前完全一致

#### Scenario: 只在 BULL 主趋势语义下应用
- **WHEN** `ctx.market_state != "BULL"` 或 `ctx.risk_on = false`
- **THEN** bull breakout quality veto SHALL 不生效

#### Scenario: 只阻断 breakout / overlap
- **WHEN** 候选 `alpha_source` 不属于 `breakout` 或 `pullback_overlap`
- **THEN** bull breakout quality veto SHALL 不生效

#### Scenario: residual_strength 不达标时阻断
- **WHEN** `bull_breakout_quality_veto_enabled = true`
- **AND** `ctx.market_state = "BULL"`
- **AND** 候选为 breakout / overlap
- **AND** `residual_strength_score < bull_breakout_quality_veto_min_residual_strength_score`
- **THEN** 该候选 SHALL 被阻断
- **THEN** 阻断 reason_code SHALL 记录为 `BLOCK_BULL_QUALITY_VETO`

#### Scenario: breakout_margin 不达标时阻断
- **WHEN** `bull_breakout_quality_veto_enabled = true`
- **AND** `ctx.market_state = "BULL"`
- **AND** 候选为 breakout / overlap
- **AND** `breakout_margin_score < bull_breakout_quality_veto_min_breakout_margin_score`
- **THEN** 该候选 SHALL 被阻断
- **THEN** 阻断 reason_code SHALL 记录为 `BLOCK_BULL_QUALITY_VETO`

### Requirement: Bull breakout quality veto AB

系统 SHALL 支持基于当前正式 `baseline_V10.2` 执行一轮最小 A/B：

- A = `baseline_V10.2`
- B = `baseline_V10.2 + bull_breakout_quality_veto`

AB 的唯一 intended diff SHALL 是：

- `bull_breakout_quality_veto_enabled = true`
- `bull_breakout_quality_veto_min_residual_strength_score`
- `bull_breakout_quality_veto_min_breakout_margin_score`

#### Scenario: intended diff 单一
- **WHEN** 运行本轮 A/B
- **THEN** 除 veto 三个字段外，其余 universe / data_role / market_filter / exit / sizing / ranking 核 SHALL 保持一致

#### Scenario: 输出正式对照产物
- **WHEN** A/B 运行完成
- **THEN** 输出目录 SHALL 至少包含：
  - `summary.json`
  - `report.md`
  - `performance_comparison.csv`
  - `bull_trade_quality_comparison.csv`
