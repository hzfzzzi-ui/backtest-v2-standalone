## Why

每次回测实验的产出散落在 `outputs/experiments/exp_*` 目录中，52 个目录（含 10 个旧格式废弃目录）平铺堆叠，无法区分正式实验与调试碎片。没有持久化的人类可读报告（报告仅在前端 JS 临时生成），也没有实验索引，必须逐个打开 JSON 文件才能了解结果。

需要一套清晰的实验产物架构：每次回测自动生成三件套（报告 + 配置 + 交易明细），支持历史浏览和结果回载。

## What Changes

### 后端
1. **新建 `report_generator.py`** — Python 端生成自包含 `report.html`（从前端 `generateReport()` 移植 HTML 模板），在 `stabilize_experiment_result()` 中自动调用
2. **持久化 `stock_names.json`** — 在 stabilize 阶段查询中文股票名并落盘，供报告生成使用
3. **`tier` 写入 `run_meta.json`** — 将策略评级持久化
4. **维护 `index.json`** — 每次回测完成后追加实验摘要到全局索引，含自动生成的可读标签
5. **新增 4 个 API 端点** — 实验列表、报告查看、单条删除、全部清空
6. **清空旧数据** — 删除所有现存实验目录，从零开始

### 前端
7. **History 面板** — Rail 新增第 5 个图标，Drawer 新增 `data-module="history"` section，展示实验卡片列表
8. **「加载结果」按钮** — 点击后将历史实验的产物加载到当前工作台（覆盖 `state.active_artifacts`）
9. **「查看报告」按钮** — 新标签页打开后端 `report.html`
10. **前端「导出报告」改为读取后端已生成的 report.html** — 不再前端拼接，只维护一份模板

## Capabilities

### New Capabilities
- `experiment-history`: 实验历史管理（索引、浏览、回载、删除）
- `server-report-gen`: 后端自动生成自包含 HTML 回测报告

### Modified Capabilities
- `backtest-report-export`: 前端「导出报告」改为读取后端 report.html，不再本地生成

## Impact

- **后端新文件**：`backend/core/report/report_generator.py`（~200 行）
- **后端修改**：`backtest_v2_artifacts.py`（stock_names + report + index 写入）、`backtest_v2.py`（4 个新 API + tier 传递）
- **前端修改**：`index.html`（Rail 图标 + History drawer section）、`backtest_v2.js`（History 面板渲染 + generateReport 改为 fetch）、`workbench.css`（History 卡片样式）
- **数据清理**：容器内 `outputs/experiments/*` 全部删除
