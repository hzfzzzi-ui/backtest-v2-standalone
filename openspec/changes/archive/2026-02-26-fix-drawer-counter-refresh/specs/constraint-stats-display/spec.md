## MODIFIED Requirements

### Requirement: Backend supplies constraint counters
结果 API 响应和 `run_meta.json` 产物 SHALL 包含全部 constraint 计数器字段。

#### Scenario: Constraint counters in run_meta.json after single run
- **WHEN** 单次回测通过 `/api/backtest_v2/experiment/run_async` 运行完成
- **THEN** `results_dir/run_meta.json` 的 `counters` 对象 SHALL 包含：
  - `avg_positions`（float）：每日平均持仓数，来自引擎 metrics
  - `slots_left`（float）：`max_positions - avg_positions`，保留 1 位小数
  - `cap_hit_single`（int）：candidates 中 reason 为 BLOCK_SINGLE_CAP 的次数
  - `cap_hit_industry`（int）：candidates 中 reason 为 BLOCK_INDUSTRY_CAP 的次数
  - `cash_skip_count`（int）：candidates 中 reason 为 SKIP_CASH_INSUFFICIENT 的次数
  - `lot_skip_count`（int）：candidates 中 reason 为 SKIP_LOT_TOO_SMALL 的次数

#### Scenario: Constraint counters default to zero when candidates file missing
- **WHEN** `portfolio_candidates.csv` 不存在或无 reject/skip reason 列
- **THEN** `cap_hit_single`、`cap_hit_industry`、`cash_skip_count`、`lot_skip_count` SHALL 默认为 0

#### Scenario: slots_left defaults when avg_positions unavailable
- **WHEN** 引擎 metrics 中不包含 `avg_positions`
- **THEN** `avg_positions` SHALL 默认为 0.0
- **THEN** `slots_left` SHALL 为 `max_positions - 0.0`
