## MODIFIED Requirements

### Requirement: DaySignals 数据类

引擎 SHALL 定义 `DaySignals` 数据类作为 `day_signals()` 的返回类型，包含：
- `sell_signals: list[Signal]`
- `buy_signals: list[Signal]`
- `raw_alpha_signals: list[Signal]`
- `composed_sell_signals: list[Signal]`
- `composed_buy_signals: list[Signal]`
- `exit_syms: set[str]`
- `strength_map: dict[str, float]`
- `mf_score_map: dict[str, float]`
- `diagnostics: dict[str, Any]`
- `exit_counts: ExitCounts`

其中 `diagnostics` SHALL 在现有稳定键之外，支持稳定透传 bull breakout veto 的诊断计数：

- `bull_breakout_quality_veto_applied`
- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

#### Scenario: bull breakout veto 诊断透传
- **WHEN** provider 在当日对 breakout 候选执行 bull breakout quality veto
- **THEN** `DaySignals.diagnostics` SHALL 包含上述 4 个稳定键
- **THEN** 缺省时这些键 SHALL 回填为 `false / 0`

#### Scenario: veto 阈值进入信号 meta
- **WHEN** bull breakout veto 启用且候选未被阻断
- **THEN** 该买入信号 `Signal.meta` SHALL 包含：
  - `bull_breakout_quality_veto_enabled`
  - `bull_breakout_quality_veto_min_residual_strength_score`
  - `bull_breakout_quality_veto_min_breakout_margin_score`

### Requirement: 统一引擎循环

引擎 SHALL 提供 `_run_unified_loop()` 函数，接收 `SignalProvider` 实例和引擎配置，执行单一日循环。

当 provider 路径为 breakout runtime 时，结果指标 SHALL 透传 bull breakout veto 的稳定计数器：

- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

#### Scenario: veto 计数进入 run_meta / metrics
- **WHEN** breakout provider 启用 bull breakout veto 并完成回测
- **THEN** `metrics` 与 `run_meta.json.counters` SHALL 包含上述 3 个计数器
