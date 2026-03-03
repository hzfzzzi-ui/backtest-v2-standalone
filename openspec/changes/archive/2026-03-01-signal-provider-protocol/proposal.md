## Why

`portfolio_simulator_strict.py` (1812 行) 仍包含两条完整的引擎循环：
- **SMA 路径** `run_vector_portfolio_backtest_strict()` ~800 行：预计算信号矩阵 + 逐日查表
- **Generic 路径** `_run_vector_portfolio_backtest_generic_signals()` ~500 行：逐日调用 `strategy.generate_signals()`

Phases 1-3 已统一 daily_row schema、提取共享原语（fills, price indices, engine exits），但**引擎循环仍然完全重复**。两路径在以下部分结构相同：
- 订单成交处理（`_process_pending_fills`）
- NAV/回撤计算（`compute_nav_snapshot`）
- Drawdown breaker
- 订单计划（`build_rebalance_orders`）
- 订单入队和日行记录

唯一真正不同的是**信号生成**（卖出信号 + 买入信号 + 诊断计数）。将信号生成抽象为可插拔接口，即可消除循环重复。

## What Changes

1. 定义 `SignalProvider` 协议和 `DaySignals` 数据类
2. 实现 `SMASignalProvider`（封装矩阵预计算 + 逐日查表 + 趋势退出 + 候选诊断）
3. 实现 `GenericSignalProvider`（封装策略调用 + 引擎退出 + 多因子快速门控）
4. 提取统一引擎循环 `_run_unified_loop()`
5. 删除旧的 `_run_vector_portfolio_backtest_generic_signals()` 函数

## Capabilities

### New Capabilities
- `signal-provider-protocol`: 信号提供者协议定义和统一引擎循环

### Modified Capabilities
- `engine-shared-primitives`: 引擎循环从两份独立实现变为单一统一循环

## Impact

- **代码消除**：~500 行重复循环代码删除，1812 行 → ~1300 行（分布在 4 个文件中）
- **架构改进**：新信号提供者只需实现 `day_signals()` 接口即可接入引擎
- **回归风险**：高 — 两条路径的回测结果必须与重构前完全一致
- **新文件**：3 个（protocol, sma_provider, generic_provider）
