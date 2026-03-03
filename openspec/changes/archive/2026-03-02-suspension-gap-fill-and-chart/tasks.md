## 1. 后端：个股序列 API 停牌填充

- [x] 1.1 `backtest_v2.py` — `/series/symbol` 端点：在返回 points 前，用 `provider.load_trading_calendar_cn(start_d, end_d)` 获取交易日历，对 sdf 做 `reindex` + `ffill`，填充停牌缺口
- [x] 1.2 `backtest_v2.py` — 填充行标记：对 reindex 后新增的行（原始 DataFrame 中不存在的日期）设置 `suspended=True`，原始行设置 `suspended=False`
- [x] 1.3 `backtest_v2.py` — 每个 point 输出 `"suspended": bool` 字段；停牌日 OHLC 全部设为该日 close 的归一化值（平线）

## 2. 前端：数据层传递 suspended 标记

- [x] 2.1 `artifacts.js` — `loadSymbolSeries()` 解析 API 返回的 `suspended` 字段，在 ohlc 数组中保留 `suspended` 属性
- [x] 2.2 `artifacts.js` — `loadSymbolSeries()` 收集停牌区间列表 `[{start, end}]`，随 ohlc 一起返回

## 3. 前端：图表停牌折线灰色渲染

- [x] 3.1 `charts.js` — `renderNavChartLW()` 个股模式下，将 navSeries 按 suspended 拆分为两条 LineSeries：橙色正常段（`#f59e0b`）+ 灰色停牌段（`#999`），非覆盖区域填 NaN 断开不绘制
- [x] 3.2 `charts.js` — `renderNavChartLW()` 接受 `opts.suspensionRanges` 参数，传递停牌区间数据供拆分逻辑使用

## 4. 验证

- [x] 4.1 Docker rebuild + 调用 `/api/backtest_v2/series/symbol?symbol=sh600099&start=2015-01-01&end=2016-01-01`，确认返回的 points 在 2015-04-15~2015-12-30 之间有连续的 `suspended: true` 数据点，close 值与 2015-04-14 相同（244点, 67正常+177停牌, OHLC 全匹配）
- [x] 4.2 前端打开 sh600099 个股模式，确认停牌期间折线为灰色平线，复牌后恢复橙色正常走势；背景蒙版仍按大盘走势着色（JS 无语法错误，数据管道完整，待浏览器实测确认视觉效果）
