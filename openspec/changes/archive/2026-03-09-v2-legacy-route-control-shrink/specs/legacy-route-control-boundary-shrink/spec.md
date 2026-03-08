## ADDED Requirements

### Requirement: Stage adapter SHALL isolate stage applicability into a dedicated internal module
后端必须把 stage adapter 的 stage 可用性判定迁移到专用内部模块，同时保持 disabled stage、route-specific applicability 和 neutral output 语义不变。

#### Scenario: Stage applicability remains equivalent after extraction
- **WHEN** stage shell 请求某个 stage 的输出
- **THEN** stage 是否启用、是否适用和 disabled stage 的判定 SHALL 与迁移前保持等价
- **AND** `legacy_adapter.py` SHALL 只保留对该 applicability 模块的委托

### Requirement: Stage adapter SHALL isolate route day controls into a dedicated internal module
后端必须把 route-specific 的 day control 计算和相关诊断计数更新迁移到专用内部模块，同时保持 `effective_max_positions`、`risk_on_today`、`market_state` 和 `trade_mode` 语义不变。

#### Scenario: Day controls remain equivalent after extraction
- **WHEN** stage adapter 为某个交易日准备 controls
- **THEN** `effective_max_positions`、`dd_state`、`benchmark_regime_on`、`risk_on_today`、`market_state` 和 `trade_mode` SHALL 与迁移前保持等价
- **AND** route/day-control 相关诊断计数 SHALL 保持同样的更新时点

### Requirement: Stage adapter SHALL isolate provider signal postprocess into a dedicated internal module
后端必须把 provider day signal 的 route-specific 后处理迁移到专用内部模块，同时保持买入信号过滤顺序和规则不变。

#### Scenario: Provider signal postprocess remains equivalent after extraction
- **WHEN** stage adapter 对 provider 返回的 day signals 做 route-specific 后处理
- **THEN** buy signal 的过滤结果 SHALL 与迁移前保持等价
- **AND** 不得改变 benchmark regime gate 和 market-filter state gate 的现有优先级

### Requirement: Route-control boundary shrink SHALL preserve the locked baseline
后端必须在每个 route/day-control 收敛步骤后继续通过锁定基线门禁。

#### Scenario: Locked baseline remains equivalent
- **WHEN** 完成一次 stage applicability、day controls 或 signal postprocess 责任迁移后复跑锁定基线请求
- **THEN** `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`、`nav.csv` 和 `config_truth` SHALL 继续为 `PASS`
- **AND** 允许的 `WARN` SHALL 仍然只限于已接受的诊断性漂移
