## 1. 回撤聚合逻辑修复

- [x] 1.1 新增 `aggregateDrawdown(dailyDd, period)` 函数 — 与 `aggregateNav` 类似但在周期桶内取 `Math.min`（最大回撤深度）而非覆盖为最后一天的值。日线模式直接返回原数组。DoD: W/M/Y 聚合时回撤值为周期内极值。验证: 构造已知周线数据手动对比。

## 2. 回撤图迁移到 LightweightCharts

- [x] 2.1 新增 `renderDdChartLW(containerId, ddSeries, benchDdSeries, showBenchmark)` 函数 — 在 `wbDdChart` 容器中创建独立 LightweightCharts 实例，策略回撤用红色 AreaSeries，基准回撤用橙色 LineSeries。Y 轴使用百分比格式化。DoD: 回撤图用 LightweightCharts 渲染且视觉风格与现有一致。验证: 跑一次回测，回撤图正确显示红色填充区域和橙色基准线。风险: AreaSeries API 在 v4.0 和 v4.2 间有差异，需兼容两种调用方式（同收益图模式）。

- [x] 2.2 修改 `renderPerfPanel()` — 将回撤图的 `renderLineChart('wbDdChart', ...)` 调用替换为 `renderDdChartLW('wbDdChart', ddSeries, benchDdSeries, showBenchmark)`，ddSeries 改用 `aggregateDrawdown` 聚合。DoD: 回撤图不再使用 SVG 渲染。验证: 切换 D/W/M/Y 周期后回撤图均正常。

## 3. 时间轴同步

- [x] 3.1 实现双图时间轴同步 — 在两个 chart 实例创建后，互相通过 `timeScale().subscribeVisibleLogicalRangeChange()` 订阅可视范围变化，收到变化时调用对方的 `timeScale().setVisibleLogicalRange()`。需加防递归标志避免无限循环。DoD: 缩放/平移任一图时另一图同步。验证: 在收益图上滚轮缩放，观察回撤图 X 轴范围同步变化。风险: 事件循环递归，需用 `_syncLock` 标志防护。

## 4. crosshair 联动

- [x] 4.1 实现双图 crosshair 联动 — 在两个 chart 实例上通过 `subscribeCrosshairMove()` 监听鼠标位置，收到 event 后调用对方 `setCrosshairPosition()` 或通过 `chart.setCrosshairPosition(price, time)` 同步。鼠标离开时调用 `clearCrosshairPosition()`。DoD: 悬停收益图时回撤图显示同一时间的 crosshair。验证: 鼠标在收益图上移动，回撤图 crosshair 跟随；移出后消失。风险: LightweightCharts v4 的 crosshair 同步 API 需确认具体方法名（`setCrosshairPosition` 可能不在所有版本中）。

## 5. 清理与 CSS 调整

- [x] 5.1 管理双 chart 实例生命周期 — 将 `_lwChart` 扩展为 `_lwChartNav` 和 `_lwChartDd`，在 `renderLoadingSkeleton()` 和重新渲染时正确销毁两个实例。DoD: 多次运行回测后无内存泄漏或残留 chart 实例。验证: 连续运行 3 次回测，每次图表正确重建。

- [x] 5.2 调整 CSS 高度分配 — 确认 `.wb-chart-main` 和 `.wb-chart-sub` 的高度比例合理（主图 ~70%，回撤图 ~30%），回撤图 container 需要足够高度给 LightweightCharts 渲染。DoD: 两图视觉比例协调。验证: 浏览器窗口不同尺寸下两图均可见且不被压缩。

## 6. Docker 端到端验证

- [x] 6.1 Docker rebuild 并运行多股票回测 — 验证收益曲线与回撤曲线同步渲染、缩放联动、周期切换均正常。DoD: 5 只股票 1.5 年回测，D/W/M 三个周期下两图 X 轴对齐。验证: 肉眼确认最大回撤点在两图中时间位置一致。
