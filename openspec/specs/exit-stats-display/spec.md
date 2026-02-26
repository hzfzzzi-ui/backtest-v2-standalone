## ADDED Requirements

### Requirement: Exit trigger statistics display
Exit Statistics 面板 SHALL 使用中文标签显示退出统计。

#### Scenario: 标签中文化
- **WHEN** Exit Statistics 面板渲染计数器
- **THEN** 标签 SHALL 为中文：反转平仓、ATR止损平仓、ATR追踪平仓、ATR追踪更新、到期平仓
- **THEN** 数值 SHALL 显示为整数格式（无小数位）

#### Scenario: Statistics populated after run
- **WHEN** a backtest run completes and results are loaded for the active group
- **THEN** the Exit stats row SHALL display: `reversal_exit_count`, `atr_stop_exit_count`, `atr_trail_exit_count`, `atr_trail_update_count`, `time_exit_count`
- **THEN** each counter SHALL show its label and numeric value

#### Scenario: Statistics empty before run
- **WHEN** no run results are available
- **THEN** each counter SHALL display "---" as placeholder

### Requirement: ATR caliber note
The Exit accordion block SHALL display a read-only ATR caliber note showing the ATR computation parameters derived from current configuration.

#### Scenario: ATR note reflects current settings
- **WHEN** the user views the Exit block
- **THEN** the note SHALL display: ATR window (14日), price adjustment (read from Universe 价格口径 setting), and trigger price (read from Universe 成交价假设 setting)

#### Scenario: ATR note updates on config change
- **WHEN** the user changes 价格口径 or 成交价假设 in the Universe module
- **THEN** the ATR note in Exit block SHALL update to reflect the new values

### Requirement: Checkbox-input linkage
Inputs associated with optional exit strategies SHALL be disabled when their corresponding checkbox is unchecked.

#### Scenario: Trail input disabled
- **WHEN** "移动止盈" checkbox (wbExitTrail) is unchecked
- **THEN** the `trail_k` input (wbTrailK) SHALL be disabled and visually dimmed
- **THEN** the `trail_k` label SHALL show unit annotation "xATR"

#### Scenario: Trail input enabled
- **WHEN** "移动止盈" checkbox is checked
- **THEN** the `trail_k` input SHALL be enabled and editable

#### Scenario: Time exit input disabled
- **WHEN** "时间退出" checkbox (wbExitTime) is unchecked
- **THEN** the `N days` input (wbExitDays) SHALL be disabled and visually dimmed

#### Scenario: Time exit input enabled
- **WHEN** "时间退出" checkbox is checked
- **THEN** the `N days` input SHALL be enabled and editable

#### Scenario: Initial state matches defaults
- **WHEN** the page first loads with default config (wbExitTrail unchecked, wbExitTime unchecked)
- **THEN** both `trail_k` and `N days` inputs SHALL be disabled

### Requirement: Backend supplies reversal and time exit counts
结果 API 响应和 `run_meta.json` 产物 SHALL 包含 `reversal_exit_count` 和 `time_exit_count` 字段，以及全部 exit 计数器。

#### Scenario: Counters present in results
- **WHEN** results are fetched for a completed run via `/api/backtest_v2/results/{run_id}`
- **THEN** the response SHALL contain `reversal_exit_count` (integer) counting sell orders triggered by signal reversal
- **THEN** the response SHALL contain `time_exit_count` (integer) counting sell orders triggered by time-based exit

#### Scenario: Counters default to zero when unavailable
- **WHEN** the underlying run data does not contain explicit reversal/time exit reason codes
- **THEN** both counters SHALL default to 0

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
