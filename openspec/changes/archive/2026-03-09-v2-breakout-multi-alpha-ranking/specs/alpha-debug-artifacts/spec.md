## ADDED Requirements

### Requirement: 系统 SHALL 输出候选级调试产物
每次启用多 alpha 候选或统一排序实验时，系统 SHALL 输出候选级调试产物，确保候选来源、分数字段和最终入选结果可追溯。

#### Scenario: candidate_signals.csv 存在
- **WHEN** 多 alpha 或排序增强运行完成
- **THEN** 结果目录 SHALL 包含 `candidate_signals.csv`
- **THEN** 该文件 SHALL 至少包含 `date`、`symbol`、`alpha_source`、`residual_strength_score`、`sector_strength_score`、`volume_price_quality_score`、`final_score`、`selected_flag`

#### Scenario: score_diagnostics.csv 存在
- **WHEN** 排序增强运行完成
- **THEN** 结果目录 SHALL 包含 `score_diagnostics.csv`
- **THEN** 该文件 SHALL 能展示每日 top candidates 及其关键分数字段

### Requirement: 系统 SHALL 输出 alpha 阶段漏斗
系统 SHALL 输出按阶段拆分的 alpha 漏斗，帮助验证“候选增加是否真的进入排序和组合层”。

#### Scenario: alpha_funnel.csv 存在
- **WHEN** 多 alpha 实验运行完成
- **THEN** 结果目录 SHALL 包含 `alpha_funnel.csv`
- **THEN** 该文件 SHALL 至少区分各阶段候选数、被淘汰数和最终入选数

### Requirement: 三阶段研究 SHALL 输出 AB 汇总
三阶段最小可证伪实验 SHALL 输出统一的横向对比表，便于对 baseline / phase1 / phase2 / phase3 做同口径比较。

#### Scenario: ab_summary.csv 存在
- **WHEN** Phase 1/2/3 研究脚本完成
- **THEN** 汇总目录 SHALL 包含 `ab_summary.csv`
- **THEN** 该文件 SHALL 至少包含原始信号数、下单数、平均持仓数、仓位利用率、CAGR、MaxDD、Sharpe、Calmar、胜率、平均持有天数

### Requirement: 订单产物 SHALL 保持可追溯
研究产物 SHALL 提供 `orders.csv`，即使底层仍复用当前成交写出逻辑，也必须能让用户追踪最终执行的委托级结果。

#### Scenario: orders.csv 可用
- **WHEN** 回测完成
- **THEN** 结果目录 SHALL 包含 `orders.csv`
- **THEN** 该文件 SHALL 至少包含日期、标的、方向、数量、价格和 reason_code 或等价委托字段
