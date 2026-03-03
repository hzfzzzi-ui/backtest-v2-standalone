## Why

右侧面板存在两个影响使用体验的问题：
1. **布局拥挤**：概览内容（摘要+KPI+个股绩效+图表）+ 底部 Dock（260px 固定）总高 ~1240px，超过 1080p 屏幕可用高度。Dock 内的交易明细、信号漏斗被压缩在 260px 空间内，滚动体验差。
2. **三个 KPI 始终为空**：卡尔马比率=0.00、Top10集中度=—、评级=— 后端从未计算，前端读取到空值。

## What Changes

- **移除底部 Dock**：删除固定 260px 的 `wb-dock` 区域及其拖拽调整逻辑
- **新增顶部双 Tab 切换**：在 `wb-main` 顶部增加 `[概览] [分析]` Tab Bar（~36px），概览和分析各占全高
- **概览 Tab**：原 `wb-main-content` 内容不变（Summary + KPI + 个股绩效 + 图表），获得 +260px 垂直空间
- **分析 Tab**：原 Dock 三个子面板（Explain / Execution / Logs）提升为全高滚动面板，保留子标签切换
- **补全 calmar 计算**：在 `_compute_metrics()` 中用 `cagr / |max_drawdown|` 计算卡尔马比率
- **补全 top10_profit_concentration 计算**：在 metrics 中按 symbol 聚合交易利润，取 Top10 占总正利润比例
- **补全 tier 评级**：在 `experiment_runner.py` 中基于 sharpe + max_drawdown + calmar 分级（T1–T4）
- **透传到 perf.json**：确保三个字段写入 perf.json 供前端读取

## Capabilities

### New Capabilities
- `dual-tab-layout`: 右侧面板双 Tab 布局（概览/分析），替代上下分割的 content+dock 结构

### Modified Capabilities
- `backtest-report-export`: perf.json 增加 `calmar`、`top10_profit_concentration`、`tier` 三个字段

## Impact

- **前端**：`index.html`（HTML 结构重组）、`workbench.css`（新增 tab 样式、删除 dock 样式）、`backtest_v2.js`（tab 切换事件）、`ui-controls.js`（switchDockTab 适配）、`artifacts.js`（tier 读取路径修复）
- **后端**：`portfolio_builder.py`（calmar + top10 计算）、`experiment_runner.py`（tier 计算 + top10 透传）、`backtest_v2_artifacts.py`（perf_obj 字段补全）
- **产物协议**：perf.json 新增 3 个字段（向后兼容，旧数据为 null/0）
- **不受影响**：`charts.js`、`report.js`、`compare.js`（DOM ID 全部保留，无需改动）
