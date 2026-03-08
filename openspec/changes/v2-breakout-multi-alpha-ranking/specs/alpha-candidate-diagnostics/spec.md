## ADDED Requirements

### Requirement: 候选与入选必须保留 alpha 来源和分数字段
系统 SHALL 在候选审计产物中保留每个候选的 alpha 来源、各分数字段和最终是否入选，保证入选原因可追溯。

#### Scenario: Candidate Signals 可追溯
- **WHEN** 研究实验以 `fast_mode=false` 运行
- **THEN** 候选产物 MUST 至少包含 `date`、`symbol`、`alpha_source`、`residual_strength_score`、`sector_strength_score`、`volume_price_quality_score`、`final_score`、`selected_flag`

#### Scenario: 最终入选可解释
- **WHEN** 某标的在交易日 `t` 被选入订单列表
- **THEN** 候选审计行 MUST 能解释它来自 breakout 还是 pullback，以及为什么在当日排序中靠前

### Requirement: 研究脚本必须输出 alpha 漏斗与 score diagnostics
系统 SHALL 在三阶段最小实验中输出新增调试文件，供研究结论复核。

#### Scenario: Alpha Funnel 输出
- **WHEN** 运行 Phase 1 / Phase 2 / Phase 3 任一研究实验
- **THEN** 系统 MUST 输出 `alpha_funnel.csv`
- **THEN** 该文件 MUST 至少包含各阶段候选数、淘汰数、最终入选数

#### Scenario: Score Diagnostics 输出
- **WHEN** 运行启用 residual 或综合排序的研究实验
- **THEN** 系统 MUST 输出 `score_diagnostics.csv`
- **THEN** 该文件 MUST 至少包含每日 top candidates 的分数字段与排序位置

### Requirement: 三阶段实验必须输出统一 AB 汇总
系统 SHALL 为 baseline、phase1、phase2、phase3 生成统一汇总表，便于横向比较。

#### Scenario: AB Summary 输出
- **WHEN** 三阶段实验全部完成
- **THEN** 系统 MUST 输出 `ab_summary.csv`
- **THEN** 表中 MUST 包含 `CAGR`、`MaxDD`、`Sharpe`、`Calmar`、`avg_positions`、`utilization`、`raw_signal`、`orders`
