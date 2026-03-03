## Why

个股序列 API (`/series/symbol`) 直接返回数据库中的稀疏数据——停牌期间数据库无行记录，导致前端图表在停牌前后两个数据点之间画直线，呈现出"匀速平滑上涨"的虚假曲线（如 sh600099 在 2015 年 4~12 月停牌期间）。用户无法区分真实趋势与数据缺口。

## What Changes

- **后端**：个股序列 API 返回数据前，用交易日历填充停牌缺口——停牌日 close 取最后交易日价格，标记 `suspended: true`
- **前端**：图表识别 `suspended` 标记，停牌期间画灰色平线，复牌后恢复正常 K 线/折线颜色

## Capabilities

### New Capabilities
- `suspension-series-fill`: 后端 API 层面的停牌日期填充与标记，确保返回给前端的个股序列在日期维度上连续
- `suspension-chart-overlay`: 前端图表对停牌区间的差异化渲染（灰色平线 + 区域标注）

### Modified Capabilities
- `benchmark-candlestick-display`: 个股模式下 K 线需要识别 suspended 标记，停牌 K 线用灰色渲染，非停牌恢复正常颜色

## Impact

- **后端**：`backtest_v2.py` 的 `/series/symbol` 端点需要查交易日历并 forward-fill
- **前端**：`charts.js` 渲染逻辑需要处理 suspended 字段；`artifacts.js` 数据加载需传递 suspended 标记
- **无引擎改动**：引擎层信号计算已自行 ffill（`regime_router_signal_provider.py:363`），交易层 NaN 价格已正确跳过，无需修改
