## MODIFIED Requirements

### Requirement: Exit trigger statistics display
Exit Statistics 面板 SHALL 使用中文标签显示退出统计，包含新增的止盈和固定止损计数器。

#### Scenario: 标签中文化
- **WHEN** Exit Statistics 面板渲染计数器
- **THEN** 标签 SHALL 为中文：反转平仓、ATR止损平仓、ATR追踪平仓、ATR追踪更新、到期平仓、止盈平仓、固定止损平仓、熔断拦截
- **THEN** 数值 SHALL 显示为整数格式（无小数位）

#### Scenario: Statistics populated after run
- **WHEN** a backtest run completes and results are loaded for the active group
- **THEN** the Exit stats row SHALL display: `reversal_exit_count`, `atr_stop_exit_count`, `atr_trail_exit_count`, `atr_trail_update_count`, `time_exit_count`, `take_profit_exit_count`, `fixed_stop_loss_exit_count`, `drawdown_breaker_block_count`
- **THEN** each counter SHALL show its label and numeric value

#### Scenario: Statistics empty before run
- **WHEN** no run results are available
- **THEN** each counter SHALL display "---" as placeholder

### Requirement: Backend supplies reversal and time exit counts
结果 API 响应和 `run_meta.json` 产物 SHALL 包含 `reversal_exit_count` 和 `time_exit_count` 字段，以及全部 exit 计数器，包括新增的止盈、固定止损和熔断计数器。

#### Scenario: Counters present in results
- **WHEN** results are fetched for a completed run via `/api/backtest_v2/results/{run_id}`
- **THEN** the response SHALL contain `reversal_exit_count` (integer) counting sell orders triggered by signal reversal
- **THEN** the response SHALL contain `time_exit_count` (integer) counting sell orders triggered by time-based exit
- **THEN** the response SHALL contain `take_profit_exit_count` (integer) counting sell orders triggered by take profit
- **THEN** the response SHALL contain `fixed_stop_loss_exit_count` (integer) counting sell orders triggered by fixed stop loss
- **THEN** the response SHALL contain `drawdown_breaker_block_count` (integer) counting buy signals blocked by circuit breaker

#### Scenario: Counters default to zero when unavailable
- **WHEN** the underlying run data does not contain explicit reason codes for new exit types
- **THEN** all new counters SHALL default to 0

#### Scenario: Counters present in run_meta.json after single run
- **WHEN** 单次回测通过 `/api/backtest_v2/experiment/run_async` 运行完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象
- **THEN** `counters` SHALL 包含 `reversal_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `time_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `atr_stop_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `atr_trail_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `atr_trail_update_count`（整数）
- **THEN** `counters` SHALL 包含 `take_profit_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `fixed_stop_loss_exit_count`（整数）
- **THEN** `counters` SHALL 包含 `drawdown_breaker_block_count`（整数）
- **THEN** `counters` SHALL 包含 `drawdown_breaker_trigger_count`（整数）
- **THEN** `counters` SHALL 包含 `drawdown_breaker_recover_count`（整数）

#### Scenario: Counters default to zero when trades file missing
- **WHEN** `portfolio_trades.csv` 不存在或为空
- **THEN** 所有 exit 计数器 SHALL 默认为 0

#### Scenario: Frontend reads counters from run_meta
- **WHEN** 前端 `loadActiveArtifacts()` 成功加载 `run_meta.json`
- **THEN** `renderExplainPanel()` 中 `art.run_meta.counters` SHALL 非空
- **THEN** `populateExitStats(counters)` SHALL 用实际数值填充 Drawer 面板，包含新增计数器
