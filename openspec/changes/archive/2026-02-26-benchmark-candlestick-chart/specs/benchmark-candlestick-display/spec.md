## ADDED Requirements

### Requirement: 使用 lightweight-charts 渲染蜡烛图与折线叠加
前端 `wbNavChart` 容器 SHALL 使用 lightweight-charts (TradingView) 库渲染图表，Benchmark 大盘指数以蜡烛图（CandlestickSeries）显示，Strategy NAV 以折线（LineSeries）叠加在同一图表中。

#### Scenario: 有 Benchmark OHLC 和 Strategy NAV 数据
- **WHEN** 回测运行完成且 API 返回 Benchmark 归一化 OHLC 数据和 Strategy NAV 序列
- **THEN** `wbNavChart` SHALL 显示 Benchmark 蜡烛图（阳线绿色、阴线红色）
- **THEN** `wbNavChart` SHALL 同时叠加 Strategy NAV 蓝色折线
- **THEN** 两个 series 共享同一 Y 轴，刻度为归一化值（~1.0 起点）

#### Scenario: Benchmark 数据为空但有 Strategy NAV
- **WHEN** API 返回 Benchmark points 为空数组，但 Strategy NAV 有数据
- **THEN** `wbNavChart` SHALL 仅显示 Strategy NAV 折线，不显示蜡烛图
- **THEN** 图表 SHALL 正常渲染，无报错

#### Scenario: 无任何数据
- **WHEN** Strategy NAV 和 Benchmark 数据均为空
- **THEN** `wbNavChart` SHALL 显示空状态占位（"运行实验后显示净值曲线"）

### Requirement: Benchmark 数据总是从 API 获取真实行情
前端 `loadBenchmarkSeries()` SHALL 总是调用 `/api/backtest_v2/series/benchmark` API 获取数据，MUST NOT 使用 artifact 文件中的预计算 benchmark_nav 数据。

#### Scenario: artifact 中存在 benchmark_nav 文件
- **WHEN** 回测产物中包含 benchmark_nav artifact 文件
- **THEN** 前端 SHALL 忽略该 artifact，调用 API 获取真实 OHLC 行情数据

#### Scenario: API 请求失败
- **WHEN** `/api/backtest_v2/series/benchmark` 请求失败（网络错误或 503）
- **THEN** 前端 SHALL 在状态栏显示 benchmark 错误信息
- **THEN** `wbNavChart` SHALL 仅显示 Strategy NAV 折线（无蜡烛图）

### Requirement: Benchmark 显示开关保持功能
现有 `wbChartBenchToggle` 开关 SHALL 继续生效，控制蜡烛图的显示与隐藏。

#### Scenario: 用户关闭 Benchmark 显示
- **WHEN** 用户取消勾选 Benchmark 显示开关
- **THEN** `wbNavChart` SHALL 仅显示 Strategy NAV 折线，蜡烛图隐藏

#### Scenario: 用户开启 Benchmark 显示
- **WHEN** 用户勾选 Benchmark 显示开关
- **THEN** `wbNavChart` SHALL 同时显示 Benchmark 蜡烛图和 Strategy NAV 折线

### Requirement: lightweight-charts 通过 CDN 引入
前端 SHALL 通过 CDN `<script>` 标签引入 lightweight-charts 库，MUST NOT 使用本地构建工具链。

#### Scenario: 页面加载
- **WHEN** 用户打开回测工作台页面
- **THEN** lightweight-charts 库 SHALL 通过 CDN 加载成功
- **THEN** 全局 SHALL 可用 `LightweightCharts` 或等效 API
