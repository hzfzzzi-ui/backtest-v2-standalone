## Why

收益曲线（wbNavChart）和回撤曲线（wbDdChart）视觉上无法对齐。收益图使用 LightweightCharts（Canvas、真实日期轴、支持缩放平移），回撤图使用 SVG 静态折线（等距序号轴、不可交互）。用户拖动/缩放收益图后回撤图不跟随，周期聚合时回撤取了末日值而非极值，两图缺乏 crosshair 联动，导致无法直观对比"某段下跌对应多大回撤"。

## What Changes

- 将回撤曲线从 SVG `renderLineChart` 迁移到 LightweightCharts Histogram/Area 系列，与收益图共享同一个 chart 实例的时间轴
- 回撤曲线作为 secondary pane（LightweightCharts pane API）或叠加在主图下方的独立 chart 实例但通过 `timeScale().subscribeVisibleLogicalRangeChange()` 实现时间轴同步
- 修复 `aggregateNav` 对回撤序列的聚合逻辑：周/月/年聚合时取周期内**最小值**（最大回撤），而非取最后一天的值
- 移除 SVG `renderLineChart` 对回撤图的调用（保留函数本身供其他图使用）

## Capabilities

### New Capabilities
- `chart-sync`: 收益曲线与回撤曲线的时间轴同步、缩放联动、crosshair 联动

### Modified Capabilities
（无已有 spec 需要修改）

## Impact

- **前端**：`frontend/assets/js/backtest_v2.js` — `renderNavChartLW()`、`renderPerfPanel()`、`aggregateNav()`、`computeDrawdownSeries()`
- **前端 HTML**：`frontend/index.html` — `wbDdChart` 容器可能需要调整结构
- **CSS**：`frontend/assets/css/workbench.css` — `.wb-chart-sub` 高度/布局可能需调整
- **后端**：无变更（数据层已验证正确）
- **依赖**：LightweightCharts（已引入，无新依赖）
