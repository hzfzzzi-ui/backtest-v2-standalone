## Why

EMA(8,55) 交叉策略在震荡市中频繁产生金叉/死叉信号，导致反复开仓止损（"打脸"）。需要在入场阶段增加趋势确认过滤：仅当 `close > slow_ma` 且 `slow_ma` 斜率为正时才允许开仓，减少逆势入场。

现有引擎的 `enable_trend_slope_filter` 作用于 MA120（长期 regime），与信号级别的 slow_ma（如 EMA55）无关。需要新增一组独立的**信号级入场过滤**参数。

## What Changes

- 新增两个入场过滤条件，可独立开关：
  - `enable_entry_above_slow_ma`: 仅当 `close > slow_ma` 时允许买入
  - `enable_entry_slow_ma_slope`: 仅当 `slow_ma` 过去 N 日斜率 > 0 时允许买入
- 新增参数 `entry_slope_lookback`（默认 5 日）控制斜率计算窗口
- 在 signal_matrix 中计算新的过滤矩阵，在引擎买入决策中应用
- 新增诊断计数器：`entry_above_slow_ma_block_count`、`entry_slope_block_count`
- 前端 Signal Generation 面板中增加入场过滤子区域
- 新建实验配置文件运行对比回测

## Capabilities

### New Capabilities
- `entry-trend-filter`: 信号级入场趋势过滤（close > slow_ma + slow_ma 斜率），包含引擎计算、参数配置、诊断计数器、前端 UI

### Modified Capabilities
- `ema-signal-engine`: 在买入信号矩阵中增加入场过滤 mask（扩展现有 signal_matrix 输出）

## Impact

- **引擎**: `signal_matrix.py` 新增 `close_above_slow` 和 `slow_ma_slope_pos` 两个布尔矩阵；`portfolio_simulator_strict.py` 在买入候选过滤中应用
- **策略**: `ema_cross.py`（及 `sma_cross_regime.py` 等）新增 `enable_entry_above_slow_ma`、`enable_entry_slow_ma_slope`、`entry_slope_lookback` 字段
- **注册表**: `registry.py` 透传新参数
- **前端**: `index.html` Signal Generation 区增加入场过滤 checkbox + lookback 输入；`backtest_v2.js` 收集并传递参数
- **配置**: 新建 `configs/plan_a_ema_cross_entry_filter.json` 运行对比回测
- **产物**: `run_meta.json` counters 增加两个 block 计数器；trades CSV 信号 meta 增加 `entry_above_slow_ma`、`slow_ma_slope` 字段
