## Context

当前回测工作台（backtest_v2.js）中的 Benchmark 大盘指数以 SVG 折线叠加在 `wbNavChart` 上，数据来源有两条路径：优先读 artifact 文件 `benchmark_nav`，fallback 调 `/api/backtest_v2/series/benchmark`。API 返回 `{ date, nav }` 格式（归一化 close），OHLC 原始数据在数据库中存在但被丢弃。

前端是纯静态 SPA（无构建工具），所有 JS 直接在 `index.html` 中通过 `<script>` 引入。图表渲染目前使用手写 SVG（backtest_v2.js 中 `renderLineChart`），dashboard.js 则使用 Chart.js。

## Goals / Non-Goals

**Goals:**
- Benchmark 大盘指数以蜡烛图（K 线）形式显示在 `wbNavChart` 中
- Strategy NAV 以折线叠加在同一张图上，与蜡烛图共享 Y 轴
- 所有数据归一化（÷ 第一天 close），蜡烛和折线刻度天然对齐
- Benchmark 数据总是来自 API 的真实数据库行情，不使用 artifact 预计算数据
- 使用 lightweight-charts (TradingView) 库，通过 CDN 引入

**Non-Goals:**
- 不改造 `wbDdChart`（回撤图保持 SVG 折线）
- 不改造 dashboard.js 中的图表（那里用 Chart.js，与此无关）
- 不增加成交量副图（仅蜡烛 + 折线）
- 不修改 benchmark_nav artifact 的生成逻辑（后端产物协议不变）

## Decisions

### D1: 图表库选择 lightweight-charts

**选择**: lightweight-charts v4 (TradingView)
**替代方案**: 手写 SVG 蜡烛、ECharts、Chart.js + 插件
**理由**:
- 体积小（~40KB gzipped），适合无构建的静态 SPA
- 专为金融图表设计，蜡烛图 + 折线叠加是一等公民
- 支持自适应容器、十字线、tooltip 等开箱即用
- CDN 引入一行即可，不需要构建工具链
- 暗色主题配置简单，与现有 workbench 深色风格一致

### D2: Benchmark 数据源 — 总是走 API

**选择**: `loadBenchmarkSeries()` 跳过 artifact 优先逻辑，总是调 API
**替代方案**: 优雅降级（artifact 有则用折线，API 有则用蜡烛）
**理由**:
- artifact 中的 benchmark_nav 是预计算归一化值，不含 OHLC → 无法画蜡烛
- 用户明确要求"不能有假数据"，必须使用数据库真实行情
- Benchmark 数据量很小（日线，几百到几千点），API 压力可忽略
- 简化前端逻辑，消除两种数据源导致的显示不一致

### D3: API 响应格式扩展

**选择**: 在现有 `{ date, nav }` 基础上追加 `open, high, low, close` 字段
**格式**:
```json
{
  "points": [
    { "date": "2024-01-02", "nav": 1.0, "open": 0.998, "high": 1.005, "low": 0.993, "close": 1.0 },
    { "date": "2024-01-03", "nav": 1.012, "open": 1.001, "high": 1.015, "low": 0.997, "close": 1.012 }
  ],
  "source": "api"
}
```
**理由**:
- 保留 `nav` 字段保持向后兼容（其他消费者可能依赖它）
- 所有 OHLC 值统一归一化（÷ 第一天 close），与 nav 同量级
- `close` 归一化值等于 `nav`，冗余但语义更清晰

### D4: lightweight-charts 容器复用 wbNavChart

**选择**: 复用现有 `#wbNavChart` div，由 lightweight-charts 接管
**理由**:
- 不新增 DOM 元素，保持 HTML 结构稳定
- 现有 `.wb-chart-main` 样式（height: 420px）直接适用
- lightweight-charts 的 `createChart` 会自动管理内部 canvas

### D5: chart 实例生命周期管理

**选择**: 在模块作用域维护 `_lwChart` 引用，每次 `renderPerfPanel` 时先 `remove()` 旧实例再创建新的
**理由**:
- lightweight-charts 不支持就地更新数据源类型（不能从 line 改 candle）
- 简单粗暴但可靠，避免复杂的实例状态管理
- `wbNavChart` 容器的 innerHTML 会被清空后重建，与现有模式一致

## Risks / Trade-offs

- **[CDN 依赖]** lightweight-charts 从 CDN 加载，离线或网络异常时不可用 → 可在未来将 js 文件下载到本地 assets 中作为 fallback
- **[归一化 OHLC 不直观]** 用户看到的蜡烛 Y 轴是 0.95~1.15 而非 3000~3500，不是传统行情软件体验 → 但与 Strategy NAV 叠加时刻度一致，这是用户选择的方案
- **[API 总是调用]** 即使有 artifact 也会多一次 API 请求 → benchmark 数据量小，延迟在 100ms 以内，可接受
- **[wbDdChart 风格不一致]** 主图用 lightweight-charts、回撤图用 SVG，风格不同 → Non-Goal，后续可按需统一
