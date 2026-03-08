## ADDED Requirements

### Requirement: multi-alpha 运行 SHALL 输出候选明细产物
当运行显式启用 pullback 或统一排序增强时，系统 SHALL 在标准回测产物之外输出候选明细产物，至少包括 `candidate_signals.csv`、`alpha_funnel.csv` 和 `score_diagnostics.csv`。

#### Scenario: candidate_signals 产物完整
- **WHEN** multi-alpha 运行完成
- **THEN** `candidate_signals.csv` SHALL 至少包含 `date`、`symbol`、`alpha_source`、`residual_strength_score`、`sector_strength_score`、`volume_price_quality_score`、`final_score`、`selected_flag`

#### Scenario: alpha_funnel 产物完整
- **WHEN** multi-alpha 运行完成
- **THEN** `alpha_funnel.csv` SHALL 至少包含按交易日和 `alpha_source` 聚合的候选数、排序前后数量、最终入选数

### Requirement: 分数诊断 SHALL 可复核最终选股原因
系统 SHALL 输出每日 top candidates 及最终入选的分数组成，供研究者验证“为什么选中/为什么落选”。

#### Scenario: score_diagnostics 包含 top candidates
- **WHEN** multi-alpha 运行完成
- **THEN** `score_diagnostics.csv` SHALL 包含每日 top candidates 的 `symbol`、`alpha_source`、各分数项、`final_score`、`selected_flag`

#### Scenario: reject reason 与分数共存
- **WHEN** 候选落选
- **THEN** 产物 SHALL 同时记录 `reject_reason` 和对应分数字段

### Requirement: AB 研究脚本 SHALL 输出阶段对比汇总
系统 SHALL 提供可复现实验脚本，按 `baseline -> phase1 -> phase2 -> phase3` 输出统一对比汇总文件。

#### Scenario: ab_summary 产物存在
- **WHEN** 三阶段最小实验完成
- **THEN** `ab_summary.csv` SHALL 至少包含 `baseline`、`phase1`、`phase2`、`phase3` 的核心指标横向对比

#### Scenario: 汇总保留实验来源
- **WHEN** `ab_summary.csv` 写出
- **THEN** 每一行 SHALL 包含对应 `exp_id`、变体名和关键配置摘要

### Requirement: orders 产物 SHALL 覆盖计划下单
当 multi-alpha 运行启用调试产物时，系统 SHALL 输出 `orders.csv`，记录组合层在 `t` 日收盘后为 `t+1` 排队的计划订单。

#### Scenario: 订单记录待执行计划
- **WHEN** 组合层生成 `pending[next_day]`
- **THEN** `orders.csv` SHALL 记录 `decision_date`、`execution_date`、`symbol`、`side`、`qty`、`reason_code` 和关键排序元数据

#### Scenario: orders 与 trades 可对照
- **WHEN** `orders.csv` 与 `portfolio_trades.csv` 同时存在
- **THEN** 研究者 SHALL 能按 `execution_date + symbol + side` 对照计划单与实际成交
