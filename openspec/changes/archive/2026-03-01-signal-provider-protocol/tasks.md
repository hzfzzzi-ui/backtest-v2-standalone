## 1. 创建 signal_provider.py — 协议 + 数据类 + 共享退出函数

- [x] 1.1 创建 `backend/core/engine_vector/signal_provider.py`，包含：SignalProvider Protocol、DayContext dataclass、DaySignals dataclass。从 `portfolio_simulator_strict.py` 移入 ExitCounts dataclass 和 `_evaluate_engine_exits()` 函数。验证：文件 < 150 行，import 无报错。
- [x] 1.2 更新 `portfolio_simulator_strict.py` 的 import：删除内联 ExitCounts / `_evaluate_engine_exits()` 定义，改为从 `signal_provider` 导入。验证：grep 确认无重复定义，现有测试/import 无报错。

## 2. 创建 GenericSignalProvider

- [x] 2.1 创建 `backend/core/engine_vector/generic_signal_provider.py`，实现 GenericSignalProvider 类。`precompute()` 封装 Generic 路径 pre-loop 设置（benchmark regime、ATR lookup、exit config 合并、multifactor gate）。`day_signals()` 封装逐日信号生成（调用 strategy.generate_signals + engine exits + strength/mf scoring + 诊断）。从 `portfolio_simulator_strict.py` 移入 `_build_multifactor_and_fast_gate()` 函数。验证：文件 < 400 行。
- [x] 2.2 从 `portfolio_simulator_strict.py` 删除 `_build_multifactor_and_fast_gate()` 函数（~90 行），确认无其他引用。

## 3. 创建 SMASignalProvider

- [x] 3.1 创建 `backend/core/engine_vector/sma_signal_provider.py`，实现 SMASignalProvider 类。`precompute()` 封装 SMA 路径 pre-loop 设置（OHLC/feature/signal 矩阵构建、候选索引、strategy 属性提取、regime/benchmark 数组、峰值状态初始化）。`day_signals()` 封装逐日信号生成（矩阵查表 sell + buy + 趋势退出 + 候选诊断 + exit counts）。验证：文件 < 500 行。

## 4. 提取统一引擎循环

- [x] 4.1 在 `portfolio_simulator_strict.py` 中提取 `_run_unified_loop()` 函数，接收 SignalProvider 实例和引擎配置参数。函数包含：日循环（fills → NAV → breaker → day_signals → rebalance → daily_row → 入队）、metrics 汇总、DataFrame 构建。验证：函数 < 400 行。
- [x] 4.2 重写 `run_vector_portfolio_backtest_strict()` 入口函数：根据 `is_sma_strategy` 选择 SMASignalProvider / GenericSignalProvider → 调用 `provider.precompute()` → 调用 `_run_unified_loop(provider, ...)`。删除旧的 `_run_vector_portfolio_backtest_generic_signals()` 函数（~520 行）和 SMA 路径内联循环代码。验证：`portfolio_simulator_strict.py` 总行数 < 650。

## 5. 回归验证

- [x] 5.1 Docker 重建，运行 SMA 回测（plan_a），对比 Phase 3 基线 exp_20260228_224829 的 4 个 CSV（daily/trades/candidates/orders）。验证：zero diff。
- [x] 5.2 运行 Generic 回测（plan_a_ema_cross），对比 Phase 3 基线 exp_20260228_224843 的 4 个 CSV。验证：zero diff。
