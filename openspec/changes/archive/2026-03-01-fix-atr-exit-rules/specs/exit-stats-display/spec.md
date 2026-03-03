## MODIFIED Requirements

### Requirement: Backend supplies reversal and time exit counts
结果 API 响应和 `run_meta.json` 产物 SHALL 包含 `reversal_exit_count` 和 `time_exit_count` 字段，以及全部 exit 计数器，包括新增的止盈、固定止损和熔断计数器。

#### Scenario: 引擎级 ATR 止损和追踪计数器
- **WHEN** 回测完成
- **THEN** 引擎 SHALL 在模拟循环中维护显式的 `atr_stop_exit_count` 和 `atr_trail_exit_count` 计数器
- **THEN** 这两个计数器 SHALL 与 `take_profit_exit_count` / `fixed_stop_loss_exit_count` 一样直接写入顶层 API 响应
- **THEN** 顶层响应 SHALL 包含 `atr_stop_exit_count`（整数）和 `atr_trail_exit_count`（整数）

#### Scenario: 引擎计数器与 reason_code 统计一致
- **WHEN** 引擎输出的 `atr_stop_exit_count` 与 reason_code CSV 后置统计的计数
- **THEN** 两者 SHALL 相等（引擎计数器为权威来源）

#### Scenario: Counters present in results
- **WHEN** results are fetched for a completed run via `/api/backtest_v2/results/{run_id}`
- **THEN** the response SHALL contain `reversal_exit_count` (integer) counting sell orders triggered by signal reversal
- **THEN** the response SHALL contain `time_exit_count` (integer) counting sell orders triggered by time-based exit
- **THEN** the response SHALL contain `take_profit_exit_count` (integer) counting sell orders triggered by take profit
- **THEN** the response SHALL contain `fixed_stop_loss_exit_count` (integer) counting sell orders triggered by fixed stop loss
- **THEN** the response SHALL contain `atr_stop_exit_count` (integer) counting sell orders triggered by ATR stop loss
- **THEN** the response SHALL contain `atr_trail_exit_count` (integer) counting sell orders triggered by ATR trailing stop
- **THEN** the response SHALL contain `drawdown_breaker_block_count` (integer) counting buy signals blocked by circuit breaker

#### Scenario: Counters present in run_meta.json after single run
- **WHEN** 单次回测通过 `/api/backtest_v2/experiment/run_async` 运行完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象
- **THEN** `counters` SHALL 包含 `atr_stop_exit_count`（整数，来源于引擎显式计数器）
- **THEN** `counters` SHALL 包含 `atr_trail_exit_count`（整数，来源于引擎显式计数器）
