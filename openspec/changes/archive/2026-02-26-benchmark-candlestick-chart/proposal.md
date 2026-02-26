## Why

当前回测工作台中大盘指数（Benchmark）以折线图显示，只展示归一化 NAV 单值，丢失了每日开高低收（OHLC）信息。量化研究需要直观看到大盘的蜡烛形态（阴阳线、上下影线），以便与策略净值曲线对比，判断策略在不同行情结构下的表现。

此外，当前 `loadBenchmarkSeries()` 优先读取 artifact 文件中的预计算 benchmark_nav，该数据经过二次加工，不是数据库中的真实行情。需要改为总是调用 API 获取数据库中的真实 OHLC 行情。

## What Changes

- 后端 API `/api/backtest_v2/series/benchmark` 扩展返回字段，在现有 `{ date, nav }` 基础上增加归一化的 `open, high, low, close` 字段
- 前端引入 [lightweight-charts](https://github.com/nicholasgasior/lightweight-charts) (TradingView) 图表库，通过 CDN 加载
- 前端 `wbNavChart` 改用 lightweight-charts 渲染：Benchmark 以蜡烛图显示，Strategy NAV 以折线叠加
- 前端 `loadBenchmarkSeries()` 移除 artifact 优先逻辑，总是走 API 获取真实行情数据
- 前端 `wbDdChart`（回撤图）保持现有 SVG 折线不变

## Capabilities

### New Capabilities
- `benchmark-candlestick-display`: 前端使用 lightweight-charts 将大盘指数以蜡烛图形式渲染，与策略 NAV 折线叠加在同一图表中

### Modified Capabilities
- `benchmark-series-api`: API 响应扩展，增加归一化 OHLC 字段（open, high, low, close），保持现有 nav 字段向后兼容

## Impact

- **后端**: `backend/api/endpoints/backtest_v2.py` — `get_benchmark_series` 端点修改返回格式
- **前端**: `frontend/index.html` — 新增 lightweight-charts CDN script 标签
- **前端**: `frontend/assets/js/backtest_v2.js` — 改造 `renderLineChart`（wbNavChart 部分）、`loadBenchmarkSeries`、`renderPerfPanel`
- **前端**: `frontend/assets/css/workbench.css` — 可能需要微调 `.wb-chart-main` 样式适配 lightweight-charts 容器
- **依赖**: 新增 lightweight-charts 外部 CDN 依赖（~40KB gzipped）
- **产物协议**: 无变化（benchmark_nav artifact 仍然生成，只是前端不再优先使用它）
