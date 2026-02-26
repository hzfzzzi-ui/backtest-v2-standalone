## 1. 后端 API 改造

- [x] 1.1 修改 `backend/api/endpoints/backtest_v2.py` 中 `get_benchmark_series` 端点，在返回的 points 中追加归一化的 `open`, `high`, `low`, `close` 字段（所有值 ÷ 第一天 close）。保留现有 `nav` 字段不变。验证：调用 API 确认返回 6 个字段且 `close == nav`。

## 2. 前端引入 lightweight-charts

- [x] 2.1 在 `frontend/index.html` 中添加 lightweight-charts v4 CDN `<script>` 标签（放在 backtest_v2.js 之前）。验证：浏览器控制台中 `window.LightweightCharts` 或等效 API 可用。

## 3. 前端数据源改造

- [x] 3.1 修改 `backtest_v2.js` 中 `loadBenchmarkSeries()` 函数，移除 artifact 优先读取逻辑，总是走 API。返回值中增加 OHLC 数据供蜡烛图使用。验证：无论 artifact 是否存在，benchmark 数据始终来自 API（检查 `benchmarkSource === 'api'`）。

## 4. 前端蜡烛图渲染

- [x] 4.1 新增 `renderNavChartLW(containerId, benchOhlc, navSeries, showBenchmark)` 函数，使用 lightweight-charts 创建图表：CandlestickSeries 渲染 Benchmark OHLC，LineSeries 渲染 Strategy NAV。包含实例生命周期管理（`_lwChart` 引用，重新渲染时先 remove 旧实例）。验证：在有数据时正确显示蜡烛 + 折线叠加。
- [x] 4.2 修改 `renderPerfPanel()` 中 `wbNavChart` 的渲染调用，从 `renderLineChart` 切换为 `renderNavChartLW`。正确传递 benchmarkOhlc 和 navSeries，并根据 `state.chart_show_benchmark` 控制蜡烛图显示/隐藏。验证：Benchmark toggle 开关生效，关闭时只显示 NAV 折线。
- [x] 4.3 处理边界情况：无 benchmark 数据时仅显示 NAV 折线；无任何数据时显示空状态占位。验证：分别测试 benchmark 为空、全部为空两种场景。

## 5. 样式适配

- [x] 5.1 确认 `#wbNavChart` 容器（`.wb-chart-main`, height: 420px）与 lightweight-charts 的自适应布局兼容。如需调整 CSS，修改 `frontend/assets/css/workbench.css`。验证：图表正确填充容器，无溢出或留白。
