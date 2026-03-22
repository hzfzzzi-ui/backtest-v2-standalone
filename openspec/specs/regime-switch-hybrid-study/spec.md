# regime-switch-hybrid-study Specification

## Purpose
TBD - created by archiving change add-regime-switch-v10-1-absnetmf-study. Update Purpose after archive.
## Requirements
### Requirement: 研究层 SHALL 支持按 `trade_mode` 拼接双策略收益
系统 SHALL 支持一个 research-only 的混合实验能力，在既有实验产物上按 `baseline_V10.1` 的 `trade_mode` 选择收益源重建混合净值。

#### Scenario: 牛市阶段使用 `V10.1`
- **WHEN** 某个交易日的 `baseline_V10.1 portfolio_daily.csv` 中 `trade_mode == TREND_MAIN`
- **THEN** 系统 MUST 使用该日 `V10.1 daily_return` 作为混合净值的当日收益

#### Scenario: 非牛市阶段使用半仓 `ABSNETMF`
- **WHEN** 某个交易日的 `baseline_V10.1 portfolio_daily.csv` 中 `trade_mode != TREND_MAIN`
- **THEN** 系统 MUST 使用 `0.5 * ABSNETMF daily_return` 作为混合净值的当日收益，并将另一半视为现金零收益

### Requirement: 研究层 SHALL 显式记录混合实验的边界与来源
系统 SHALL 在产物中明确记录该混合实验是研究壳拼接结果，而不是正式引擎交易结果，并记录两条底层结果源与各自的数据口径。

#### Scenario: 产物记录底层来源
- **WHEN** 混合实验完成
- **THEN** `summary.json` MUST 包含 `baseline_exp_id`、`abs_run_id`、`baseline_data_role`、`abs_data_role` 与 `research_only=true`

#### Scenario: 产物记录切换统计
- **WHEN** 混合实验完成
- **THEN** 系统 MUST 输出切换次数、牛市天数、非牛市天数和切换日志

### Requirement: 研究层 SHALL 输出可审计的混合净值产物
系统 SHALL 输出足够的研究产物，让用户可以验证每日到底使用了哪条收益源，以及总体绩效如何。

#### Scenario: 输出最小产物集合
- **WHEN** 混合实验完成
- **THEN** 系统 MUST 输出 `perf.json`、`hybrid_nav.csv`、`switch_log.csv`、`summary.json` 和 `report.md`

#### Scenario: 混合净值用统一初始资金递推
- **WHEN** 重建混合净值
- **THEN** 系统 MUST 从统一初始资金开始按选中的日收益递推，而不是直接混合两条原始绝对 NAV

