## Why

当前工作台只能查看组合级净值/回撤，无法在回测结束后快速定位“哪些个股贡献收益、哪些个股拖累回撤”。研究和复盘时需要在同一页面完成个股筛选、收益排序、买卖点与大盘对照，降低人工导出与二次分析成本。

## What Changes

- 新增回测后“按个股收益排序”的分析视图，支持个股筛选与排序（默认收益从高到低）。
- 新增个股级绩效口径（快速口径）：
  - 已平仓部分按成交配对计算；
  - 未平仓部分按回测区间最后交易日收盘价近似估值并计入个股收益。
- 新增个股回撤计算与展示，用于与收益同屏对比。
- 新增个股行情序列接口（用于前端绘制个股曲线并与基准对照）。
- 在主图叠加交易标记：买入显示绿色上箭头，卖出显示红色下箭头，支持按选中个股过滤。
- 回测产物新增个股汇总文件（如 `symbol_performance.json/csv`），并纳入 artifacts 协议供前端读取。

## Capabilities

### New Capabilities

- `symbol-performance-ranking`: 回测后输出并展示个股收益/回撤/交易次数等指标，支持筛选与收益排序。
- `trade-markers-overlay`: 在个股与基准对照曲线上叠加买卖箭头标记，并保证时间轴一致。

### Modified Capabilities

- `benchmark-candlestick-display`: 主图从“仅组合净值对基准”扩展为“可切换个股对基准”并支持交易标记叠加。

## Impact

- 后端：
  - `backend/core/analytics/*`（新增个股汇总口径与未平仓近似估值逻辑）
  - `backend/api/endpoints/backtest_v2.py`（新增个股序列 API 与产物读取字段）
  - `backend/api/endpoints/backtest_v2_artifacts.py`（写入/登记 `symbol_performance` 产物）
- 前端：
  - `frontend/assets/js/backtest_v2.js`（新增个股筛选榜单、排序、曲线叠加与买卖箭头）
  - `frontend/index.html`（新增个股分析区域控件）
- 产物与协议：
  - 新增 `symbol_performance` 产物字段；前端通过现有 artifacts/read 协议读取。
