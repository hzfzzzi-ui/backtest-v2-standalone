## ADDED Requirements

### Requirement: Breakout 缓冲带实验必须保持单一主改动
系统必须提供一套以 V9.1 baseline 为锚点的实验执行方式，并且候选配置与 baseline 的差异仅允许出现在 `strategy.params.breakout_entry_buffer_pct`。

#### Scenario: 候选配置出现未授权漂移
- **WHEN** 研究脚本构造出的候选配置与 baseline 相比，在允许路径之外存在字段差异
- **THEN** 脚本必须中止运行，并报告发生漂移的配置路径

#### Scenario: 候选配置仅修改突破缓冲带
- **WHEN** 候选配置与 baseline 的差异仅为 `strategy.params.breakout_entry_buffer_pct`
- **THEN** 脚本必须允许该实验继续执行

### Requirement: Breakout 缓冲带实验必须可复现
系统必须提供一个可重复执行的研究脚本，固定 V9.1 baseline 的股票池、成本、执行方式和退出规则，只对突破缓冲带参数运行最小对照实验。

#### Scenario: 执行最小对照实验
- **WHEN** 研究脚本被执行
- **THEN** 系统必须至少运行 baseline、`0.005` 和 `0.01` 三个缓冲带变体

#### Scenario: 运行时口径保持不变
- **WHEN** 研究脚本为任一缓冲带变体构造运行配置
- **THEN** 股票池、基准、成本、执行口径和退出配置必须继承自 V9.1 baseline

### Requirement: Breakout 缓冲带实验必须输出可审计摘要
研究脚本必须输出结构化摘要，记录每个变体的实验标识、结果目录和核心绩效指标，便于后续审计与归档。

#### Scenario: 生成结构化汇总
- **WHEN** 研究脚本完成全部变体运行
- **THEN** 系统必须写出包含 `exp_id`、`results_dir`、`cagr`、`max_drawdown`、`sharpe`、`calmar`、`trades`、`turnover` 和 `avg_positions` 的汇总文件

#### Scenario: 汇总中标明主改动
- **WHEN** 脚本写出汇总文件
- **THEN** 汇总内容必须明确记录唯一允许的主改动路径是 `strategy.params.breakout_entry_buffer_pct`
