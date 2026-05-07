# dead-code-removal Specification

## Purpose

TBD -- Remove dead code (zero-reference directories, files, and functions) from the codebase to reduce complexity and maintenance burden.
## Requirements
### Requirement: 删除零引用整目录

系统 SHALL 删除以下零引用目录，这些目录中没有任何文件被活跃代码 import：
- `backend/core/buses/` — 未接入的实验总线克隆
- `backend/core/execution/` — 被 `engine_vector` 完全取代的旧执行引擎

#### Scenario: buses 目录删除后系统正常启动
- **WHEN** `backend/core/buses/` 整目录被删除
- **THEN** Docker 容器正常启动，所有 API 路由返回正确响应，无 ImportError

#### Scenario: execution 目录删除后系统正常启动
- **WHEN** `backend/core/execution/` 整目录被删除
- **THEN** Docker 容器正常启动，回测执行正常产出 trades/nav/perf 产物

### Requirement: 删除 analytics 死文件

系统 SHALL 删除 `backend/core/analytics/` 中除 `symbol_performance.py` 和 `__init__.py` 外的所有文件：
`report.py`, `equity.py`, `export.py`, `conclusions.py`, `summary.py`, `benchmark_curve.py`, `trade_pnl.py`, `trade_concentration.py`, `schema.py`

#### Scenario: analytics 瘦身后 symbol_performance 正常工作
- **WHEN** analytics 死文件被删除，仅保留 `symbol_performance.py` 和 `__init__.py`
- **THEN** `backtest_v2_artifacts.py` 中 `from backend.core.analytics.symbol_performance import build_symbol_performance` 正常工作

### Requirement: 删除 portfolio 死文件

系统 SHALL 删除 `backend/core/portfolio/` 中以下零引用文件：
`account.py`, `ledger.py`, `positions.py`, `snapshots.py`, `sizing.py`

保留 `portfolio_builder.py`, `selection_order.py`, `__init__.py`。

#### Scenario: portfolio 瘦身后回测执行正常
- **WHEN** portfolio 死文件被删除
- **THEN** `run_portfolio_backtest()` 和 `build_rebalance_orders()` 正常被 `experiment_runner.py` 和 `portfolio_simulator_strict.py` 调用

### Requirement: 删除零引用策略文件

系统 SHALL 删除 `backend/core/strategies/sma_cross_multifactor.py` — registry 对该策略名 raise ValueError，从未被实例化。

#### Scenario: 废弃策略删除后 registry 正常
- **WHEN** `sma_cross_multifactor.py` 被删除
- **THEN** `build_strategy()` 对所有已注册策略名（sma_cross, ema_cross, ma_trend_filter 等）返回正确策略实例

### Requirement: 删除 tools 死文件

系统 SHALL 删除 `backend/core/tools/walkforward.py` 和 `backend/core/tools/univote_v2.py` — 两者均无外部调用者。

#### Scenario: tools 瘦身后 experiment_runner 正常
- **WHEN** walkforward.py 和 univote_v2.py 被删除
- **THEN** `run_experiment()` 正常执行回测流程

### Requirement: 删除 data 死文件

系统 SHALL 删除：
- `backend/core/data/calendar.py` — 日历逻辑通过 provider 方法访问
- `backend/core/data/memory_provider.py` — 无外部使用
- `backend/core/data/snapshot.py` — 仅被死掉的 `analytics/report.py` 引用

#### Scenario: data 瘦身后 pg_provider 正常
- **WHEN** data 死文件被删除
- **THEN** `PostgresDataProvider` 正常加载行情数据、交易日历、ST 历史

### Requirement: 删除 backtest_v2.py 内孤立函数

系统 SHALL 删除 `backtest_v2.py` 中以下无调用者函数（约 630 行）：
- `normalize_row`, `_parse_ps_object_row`
- `_resolve_candidate_dir`, `_to_rel`
- `_write_nav_csv`, `_write_funnel_csv`, `_write_reason_code_counts_csv`
- `_infer_universe_size`, `build_run_meta`, `_infer_manifest_dims`
- `_extract_trigger_counters`
- Legacy run 子系统：`_build_runtime_config`, `_run_backtest_v2`, `_read_validation_audit`, `_validation_warnings_to_strings`, `_write_data_validation_section`

#### Scenario: 孤立函数删除后所有路由正常
- **WHEN** 上述孤立函数被删除
- **THEN** 所有 19 个 `@router` 路由正常工作，无 NameError

### Requirement: 执行边界清理不得先于替代路径稳定
系统 SHALL 在 `dead-code-removal` 中明确：执行边界残留清理必须以后继正式路径已经稳定落地为前提，不得提前删除仍承担 compat 作用的代码。

#### Scenario: 仍有 compat 作用的残留不得被提前删除
- **WHEN** 某段旧合同或 helper 仍承担 compat 或回退作用
- **THEN** 系统 MUST 不得将其提前删除

