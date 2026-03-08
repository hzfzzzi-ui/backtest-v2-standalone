## ADDED Requirements

### Requirement: Stage adapter SHALL isolate fill accounting into a dedicated internal module
后端必须把 stage adapter 的开盘成交、现金/仓位更新、均价更新和 trade row 组装迁移到专用内部模块，同时保持公开入口与成交口径不变。

#### Scenario: Open fills remain equivalent after extraction
- **WHEN** stage adapter 在某个交易日开盘执行上一交易日挂单
- **THEN** 开盘成交、现金变化、持仓变化、均价变化和 trade row 字段 SHALL 与迁移前保持等价
- **AND** `legacy_adapter.py` SHALL 只保留对该 accounting 模块的委托，而不是继续内嵌完整成交实现

### Requirement: Stage adapter SHALL isolate daily NAV snapshot assembly into a dedicated internal module
后端必须把 stage adapter 的日度 NAV 快照、turnover、gross exposure、top holdings 和 daily row 组装迁移到专用内部模块，同时保持 `t` 日收盘评估、`t+1` 日开盘成交的时序不变。

#### Scenario: Daily snapshot remains equivalent after extraction
- **WHEN** stage adapter 为某个交易日准备 `day context`
- **THEN** NAV、market value、drawdown、turnover、gross exposure 和 daily row 字段 SHALL 与迁移前保持等价
- **AND** `prev_nav`、`peak_nav` 和 `_traded_value_today` 的更新时点 SHALL 不改变

### Requirement: Stage adapter SHALL isolate result bridging into a dedicated internal module
后端必须把 `PortfolioBacktestResult` 的 DataFrame 组装、指标桥接和 metrics augment 迁移到专用内部模块，同时保持实验产物核心字段不变。

#### Scenario: Result bridge remains equivalent after extraction
- **WHEN** stage adapter 把运行结果导出为 `PortfolioBacktestResult`
- **THEN** `daily`、`trades`、`candidates` 和 `metrics` 的核心字段 SHALL 与迁移前保持等价
- **AND** 不得改变当前基线门禁比较的核心文件名和语义

### Requirement: Accounting boundary shrink SHALL preserve the locked baseline
后端必须在每个 accounting 边界收敛步骤后继续通过锁定基线门禁。

#### Scenario: Locked baseline remains equivalent
- **WHEN** 完成一次 accounting、daily snapshot 或 result bridge 责任迁移后复跑锁定基线请求
- **THEN** `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`、`nav.csv` 和 `config_truth` SHALL 继续为 `PASS`
- **AND** 允许的 `WARN` SHALL 仍然只限于已接受的诊断性漂移
