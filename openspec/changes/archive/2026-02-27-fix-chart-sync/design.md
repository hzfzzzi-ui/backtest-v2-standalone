## Context

当前收益曲线和回撤曲线使用两套完全不同的渲染引擎：

| 维度 | 收益图 (wbNavChart) | 回撤图 (wbDdChart) |
|------|--------------------|--------------------|
| 渲染引擎 | LightweightCharts v4 (Canvas) | 自制 SVG `renderLineChart` |
| X 轴 | 真实日期轴 | 等距序号轴 |
| 交互 | 缩放、平移、crosshair | 无 |
| 聚合 | `aggregateNav` 取末日值 | 同上（回撤也取末日值） |

后端数据已验证完全正确（nav 与 drawdown 数值一致），问题纯在前端渲染层。

## Goals / Non-Goals

**Goals:**
- 收益曲线和回撤曲线 X 轴完全同步：缩放、平移、crosshair 联动
- 周期聚合（W/M/Y）时回撤取极值而非末日值
- 保持现有视觉风格（蓝色策略线、红色回撤线、橙色基准回撤线）

**Non-Goals:**
- 不修改后端数据计算逻辑（已验证正确）
- 不重构 `renderLineChart` SVG 函数（保留供其他场景使用）
- 不引入新的 npm 依赖（继续使用 CDN 引入的 LightweightCharts v4）

## Decisions

### 决策 1：回撤图使用独立 LightweightCharts 实例 + 时间轴同步

**选定方案**：创建第二个 LightweightCharts 实例渲染回撤图，通过 `timeScale().subscribeVisibleLogicalRangeChange()` 双向同步两个图的可视范围。

**备选方案 A**：在同一个 chart 实例中用 secondary price scale。
- 否决原因：收益图和回撤图量级完全不同（收益 0.8~1.2 vs 回撤 -0.04~0），共享一个 chart 会导致 Y 轴标签混乱。LightweightCharts v4 不支持多 pane。

**备选方案 B**：将回撤画为主图的 overlay（用右侧第二个 price scale）。
- 否决原因：回撤是负值区间，与正值的净值/K线共享视区会压缩两者的可视范围，不利于分析。

### 决策 2：crosshair 联动

通过 `subscribeCrosshairMove()` 在两个 chart 实例间同步鼠标位置。当用户悬停收益图时，回撤图自动显示同一时间的 crosshair，反之亦然。

### 决策 3：回撤聚合逻辑修复

新增 `aggregateDrawdown(dailyDd, period)` 函数，与 `aggregateNav` 分离。回撤序列在周期聚合时取**周期内最小值**（即最大回撤），而非取最后一天的值。

### 决策 4：回撤系列类型

使用 LightweightCharts 的 `AreaSeries`（填充区域）渲染回撤，topColor 透明、bottomColor 半透明红色、lineColor 红色。这比 Histogram 更适合展示连续回撤曲线。

## Risks / Trade-offs

**[性能] 双 chart 实例内存开销** → 回撤数据量与收益相同（~340 点/年），LightweightCharts 单实例极轻量，可忽略。

**[兼容] LightweightCharts v4 API 变动** → `subscribeVisibleLogicalRangeChange` 和 `subscribeCrosshairMove` 是 v4 稳定 API，CDN 引入已锁定 v4 主版本。

**[视觉] 两图高度分配** → 收益图占主区域（~70%），回撤图占下方（~30%）。需要调整 CSS `.wb-chart-main` 和 `.wb-chart-sub` 的高度比例，确保回撤图不被压缩太小。
