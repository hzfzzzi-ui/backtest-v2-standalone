## Why

`regime_router` 策略走 GenericSignalProvider 路径，每天调用 `strategy.generate_signals()` 在 Python 循环中重新计算所有历史的滚动 MA、RSI。复杂度为 O(N×D²)，800 只股票 × 2400 交易日耗时 360 秒，严重阻碍参数扫描。同样的数据量，向量化 SMA 路径只需 17-29 秒。根本原因是信号生成未预计算——每天为每只股票重建 groupby + sort + rolling，绝大部分计算是冗余的。

## What Changes

- 新增 `RegimeRouterSignalProvider`，实现 `SignalProvider` 协议，在 `precompute()` 阶段一次性构建 regime 状态数组、SMA 交叉矩阵、RSI 交叉矩阵；`day_signals()` 仅读取预计算矩阵行 + 管理 MR 持仓状态
- 修改 `portfolio_simulator_strict.py` 的 dispatch 逻辑，`RegimeRouter` 实例使用新 provider 而非 `GenericSignalProvider`
- 不修改 `RegimeRouter` 策略本身、不修改 `GenericSignalProvider`（保持后备兼容）

## Capabilities

### New Capabilities
- `regime-router-vectorize`: RegimeRouter 信号生成的向量化实现，将 O(N×D²) 降至 O(N×D)，目标加速 100x+

### Modified Capabilities

（无现有 spec 变更）

## Impact

- 新增文件：`backend/core/engine_vector/regime_router_signal_provider.py`
- 修改文件：`backend/core/engine_vector/portfolio_simulator_strict.py`（dispatch 逻辑，约 5 行）
- 复用现有：`FeatureMatrices`（RSI 已预计算）、`OhlcMatrices`、`build_signal_matrices`、`evaluate_engine_exits`
- 无 API 变更、无前端变更、无配置格式变更
- 回归要求：同参数配置下，向量化路径与 GenericSignalProvider 路径的 trades/daily CSV 必须零差异
