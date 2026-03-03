## Why

系统已完成引擎统一、交易成本接入、Parquet 缓存加速。现在需要用实际数据验证 `regime_router` 策略（趋势市 SMA + 震荡市 RSI + ATR 止损）的最优参数区间，为后续实盘参数选择提供数据支撑。避免过拟合，采用分层扫描：固定 regime_ma 和 SMA 参数，分别扫描 RSI 和 ATR 两个维度。

## What Changes

- 新增 16 组回测配置文件（4 RSI × 2 universe + 4 ATR × 2 universe），覆盖 `regime_router` 策略在 CSI 800 和全 A 股两个 universe 下的参数空间
- 新增批量实验运行脚本，按顺序执行所有配置并收集结果
- 新增结果汇总脚本，从各实验产物中提取关键指标（总收益、最大回撤、夏普比率、换手率、胜率），生成对比表

## Capabilities

### New Capabilities
- `batch-experiment-runner`: 批量执行多组回测配置的脚本能力，支持顺序执行、结果收集、异常恢复
- `param-sweep-report`: 参数扫描结果汇总，从多个实验产物中提取关键指标生成对比表

### Modified Capabilities

（无现有 spec 变更）

## Impact

- 新增文件：`backend/configs/sweep/` 下 16 个 JSON 配置
- 新增文件：`backend/core/tools/batch_runner.py`（批量运行脚本）
- 新增文件：`backend/core/tools/sweep_report.py`（结果汇总脚本）
- 依赖：现有 `experiment_runner.py`、`regime_router` 策略、`CachedDataProvider`
- 无 API 变更、无前端变更、无数据库变更
