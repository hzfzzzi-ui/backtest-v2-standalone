## MODIFIED Requirements

### Requirement: 扁平化结果结构
API 返回的 result SHALL 为扁平结构：顶层包含 `exp_id`、`results_dir`、`status`、metrics 字段（cagr、sharpe、max_drawdown、trades 等）、以及 `artifacts` 字典。不再包含 `rows[]` 数组和 `group_id`。result 顶层还 SHALL 包含引擎产出的计数器字段，以便前端 fallback 使用。

#### Scenario: 结果包含必要 metrics
- **WHEN** 回测成功完成
- **THEN** result 顶层包含 `cagr`（float|null）、`sharpe`（float|null）、`max_drawdown`（float）、`trades`（int）、`total_return`（float）

#### Scenario: 结果包含引擎计数器字段
- **WHEN** 回测成功完成
- **THEN** result 顶层 SHALL 包含 `avg_positions`（float）、`trend_slope_block_count`（int）、`mf_rank_applied_rate`（float）、`mf_gate_on_rate`（float）
- **THEN** result 顶层 SHALL 包含 `take_profit_exit_count`（int）、`fixed_stop_loss_exit_count`（int）、`drawdown_breaker_block_count`（int）

#### Scenario: 结果包含 artifacts 路径
- **WHEN** 回测成功完成
- **THEN** result.artifacts 包含 `perf`、`nav`、`funnel`、`reason_codes`、`config`、`run_meta`、`trades`、`symbol_performance` 八个键，值为相对于 results_dir 的文件路径
- **THEN** 若 `portfolio_daily.csv` 存在，result.artifacts 还 SHALL 包含 `daily` 键

#### Scenario: run_meta.json 包含 counters
- **WHEN** 回测成功完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象，含全部 exit 和 constraint 计数器
- **THEN** `counters` SHALL 使用短名口径：`raw_signal`、`blocked`、`orders`、`skipped`、`closed_trades`
- **THEN** `counters` SHALL 包含新增风控计数器：`take_profit_exit_count`、`fixed_stop_loss_exit_count`、`drawdown_breaker_block_count`、`drawdown_breaker_trigger_count`、`drawdown_breaker_recover_count`

#### Scenario: 不包含 rows 数组
- **WHEN** 回测成功完成
- **THEN** result 中不存在 `rows` 字段

## ADDED Requirements

### Requirement: 多实验对比 API
系统 SHALL 提供批量读取多个实验 perf 和 nav 的 API 端点，避免前端逐个请求。

#### Scenario: 批量读取 perf
- **WHEN** 前端 POST `/api/backtest_v2/experiments/compare` 并提供 `exp_ids` 列表（2-5 个）
- **THEN** 后端 SHALL 返回各实验的 `perf.json` 数据，按 exp_id 索引
- **THEN** 若某实验产物缺失，对应值 SHALL 为 null

#### Scenario: 批量读取 nav
- **WHEN** 请求中 `include_nav` 为 true
- **THEN** 响应 SHALL 额外包含各实验的 nav 序列（date, nav 数组）
- **THEN** nav 数据 SHALL 已按日期排序
