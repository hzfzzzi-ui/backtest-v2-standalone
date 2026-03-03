# market-state-chart-overlay

在 LightweightCharts 收益率图表上绘制市场状态半透明色带蒙版。

## ADDED Requirements

### Requirement: MarketStateOverlay LWC Primitive

系统 SHALL 实现 LightweightCharts v4 Series Primitive (`MarketStateOverlay`)，在收益率&大盘 K 线图底层绘制市场状态色带。

色带 SHALL 覆盖图表全高，zOrder 为 `bottom`（在 K 线和 NAV 曲线下方）。

#### Scenario: Primitive 挂载
- **WHEN** 回测完成且 market_state 数据可用
- **THEN** 系统 SHALL 将 MarketStateOverlay 实例通过 `series.attachPrimitive()` 挂载到 K 线 series 上

#### Scenario: 图表滚动/缩放时重绘
- **WHEN** 用户滚动或缩放图表时间轴
- **THEN** LWC SHALL 自动调用 primitive renderer 重绘色带（LWC 内置行为）

### Requirement: A 股配色规则

色带颜色 SHALL 遵循 A 股红涨绿跌惯例：
- **TREND_MAIN** (BULL): `rgba(220, 38, 38, 0.08)` — 半透明红
- **TREND_LIGHT** (过渡态+信号): `rgba(220, 38, 38, 0.05)` — 半透明浅红
- **BEAR**: `rgba(22, 163, 74, 0.08)` — 半透明绿
- **NO_TRADE from TRANSITION**: 透明（不绘制）

#### Scenario: BULL 区间显示红色蒙版
- **WHEN** 图表时间范围包含 BULL 状态的交易日
- **THEN** 对应区间 SHALL 显示半透明红色 (`rgba(220,38,38,0.08)`) 背景色带

#### Scenario: TREND_LIGHT 区间显示浅红色蒙版
- **WHEN** 图表时间范围包含 TREND_LIGHT 状态的交易日
- **THEN** 对应区间 SHALL 显示半透明浅红色 (`rgba(220,38,38,0.05)`) 背景色带

#### Scenario: BEAR 区间显示绿色蒙版
- **WHEN** 图表时间范围包含 BEAR 状态的交易日
- **THEN** 对应区间 SHALL 显示半透明绿色 (`rgba(22,163,74,0.08)`) 背景色带

#### Scenario: 过渡无信号区间留空
- **WHEN** 图表时间范围包含 NO_TRADE(非 BEAR) 状态的交易日
- **THEN** 对应区间 SHALL 不绘制任何色带

### Requirement: 连续状态合并绘制

Renderer SHALL 将连续相同 trade_mode 的交易日合并为一个矩形绘制，避免逐日绘制导致的性能问题和视觉缝隙。

#### Scenario: 连续 BULL 合并
- **WHEN** 连续 30 个交易日均为 TREND_MAIN
- **THEN** renderer SHALL 绘制一个完整矩形覆盖整个区间，而非 30 个独立矩形

### Requirement: 色带数据来源

色带数据 SHALL 从后端 daily_row 中的 `market_state` + `trade_mode` 字段解析，在 `artifacts.js` 中转换为 `[{time, mode}]` 数组传入 `renderNavChartLW()` 的 `opts.marketStates` 参数。

需区分 BEAR 的 NO_TRADE 和 TRANSITION 的 NO_TRADE：
- market_state == "BEAR" → mode = "BEAR"
- market_state in ("TRANS_DOWN", "TRANS_UP") 且 trade_mode == "NO_TRADE" → mode = "NO_TRADE_TRANS"（透明）

#### Scenario: 数据解析
- **WHEN** nav.csv 包含 market_state 和 trade_mode 列
- **THEN** artifacts.js SHALL 将每行转换为 `{time, mode}` 并传入图表渲染函数

#### Scenario: 数据不可用时不显示
- **WHEN** market_filter 未启用或 daily_row 不含 market_state 字段
- **THEN** 图表 SHALL 不挂载 MarketStateOverlay，行为与改动前一致

### Requirement: Drawdown 图表同步蒙版

MarketStateOverlay SHALL 同时挂载到 drawdown 图表 (`wbDdChart`)，色带区间与主图表通过 `setupChartSync()` 自动对齐。

#### Scenario: 双图表色带同步
- **WHEN** 主图表和 drawdown 图表均已渲染
- **THEN** 两个图表 SHALL 显示完全相同时间范围的市场状态色带
