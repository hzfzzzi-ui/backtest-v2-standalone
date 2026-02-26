## MODIFIED Requirements

### Requirement: Backend supplies reversal and time exit counts
结果 API 响应和 `run_meta.json` 产物 SHALL 包含 `reversal_exit_count` 和 `time_exit_count` 字段，以及全部 exit 计数器。

#### Scenario: Counters present in run_meta.json after single run
- **WHEN** 单次回测通过 `/api/backtest_v2/experiment/run_async` 运行完成
- **THEN** `results_dir/run_meta.json` SHALL 包含 `counters` 对象
- **THEN** `counters` SHALL 包含 `reversal_exit_count`（整数），统计 exit_reason 为 SIGNAL_REVERSE 或 SMA_CROSS_DOWN 的卖出次数
- **THEN** `counters` SHALL 包含 `time_exit_count`（整数），统计 exit_reason 为 TIME_EXIT 的卖出次数
- **THEN** `counters` SHALL 包含 `atr_stop_exit_count`（整数），统计 exit_reason 为 ATR_STOP_LOSS 的卖出次数
- **THEN** `counters` SHALL 包含 `atr_trail_exit_count`（整数），统计 exit_reason 为 ATR_TRAIL_EXIT 的卖出次数
- **THEN** `counters` SHALL 包含 `atr_trail_update_count`（整数），来自引擎 metrics

#### Scenario: Counters default to zero when trades file missing
- **WHEN** `portfolio_trades.csv` 不存在或为空
- **THEN** 所有 exit 计数器 SHALL 默认为 0

#### Scenario: Frontend reads counters from run_meta
- **WHEN** 前端 `loadActiveArtifacts()` 成功加载 `run_meta.json`
- **THEN** `renderExplainPanel()` 中 `art.run_meta.counters` SHALL 非空
- **THEN** `populateExitStats(counters)` SHALL 用实际数值填充 Drawer 面板
