## Why

纯趋势策略（SMA Cross）在 A 股全周期回测中 CAGR 仅 2-3%，震荡/熊市（2021-2023）中近乎零收益，严重拖累整体表现。引擎已有 benchmark-based regime 检测（risk_on = 沪深300 > MA120），但检测到震荡市后只会清仓坐等，白白浪费了震荡市的均值回归机会。需要一个自适应策略：趋势市用 SMA 交叉跟踪趋势，震荡市自动切换为 RSI 均值回归捕捉反弹，模式切换完全基于历史数据（无未来函数）。

## What Changes

- 新增 `AdaptiveRegimeStrategy` 策略类，根据 benchmark regime 状态自动路由到趋势子策略或均值回归子策略
- 在 features.py 中新增 RSI 计算矩阵（为均值回归模式提供指标）
- 在 registry.py 中注册新策略
- 前端 workbench 新增策略选项（ADAPTIVE_REGIME）及对应参数面板
- API 层 `_build_runtime_cfg_from_workbench` 新增策略编译路径

## Capabilities

### New Capabilities
- `adaptive-regime-strategy`: 自适应市场状态策略——根据 benchmark 实时 regime 信号自动在趋势跟踪模式（SMA Cross）和均值回归模式（RSI Reversal）之间切换
- `rsi-feature-matrix`: 向量化 RSI 特征矩阵计算，为均值回归信号提供底层指标

### Modified Capabilities
- `single-run-pipeline`: 策略注册表新增 adaptive_regime 类型，API workbench 编译路径新增 ADAPTIVE_REGIME 策略包

## Impact

- **后端策略层**: 新增 `backend/core/strategies/adaptive_regime.py`
- **特征计算层**: 修改 `backend/core/engine_vector/features.py`（新增 RSI 矩阵）
- **策略注册**: 修改 `backend/core/strategies/registry.py`
- **API 编译**: 修改 `backend/api/endpoints/_experiment_runner_api.py`
- **前端**: 修改 `frontend/assets/js/ui-controls.js`（策略选择器 + 参数面板）
- **走 generic_signals 路径**: 该策略不走 vectorized SMA 快速路径，走通用 per-day signal 路径
