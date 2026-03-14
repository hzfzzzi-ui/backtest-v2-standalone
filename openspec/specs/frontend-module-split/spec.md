# frontend-module-split

## Purpose

TBD -- Split the monolithic `backtest_v2.js` frontend file into focused modules for better maintainability and separation of concerns.

## Requirements

### Requirement: 提取报告生成模块 report.js

系统 SHALL 将 `generateReport()` 及其所有内部辅助函数提取到 `frontend/assets/js/report.js`：
- `buildMonthlyReturns`, `buildDrawdownAnalysis`, `buildTradeAnalysis`
- `buildPositionAnalysis`, `buildConfigSummary`, `buildTradeAppendix`

该模块完全自包含，不依赖全局 `state` 对象（通过参数传入 `result` 和 `art`）。

#### Scenario: 报告导出功能正常
- **WHEN** 用户点击"导出报告"按钮
- **THEN** 生成的 HTML 报告包含概览、月度收益、回撤分析、交易明细等完整内容

### Requirement: 提取图表渲染模块 charts.js

系统 SHALL 将 LightweightCharts 相关逻辑提取到 `frontend/assets/js/charts.js`：
- `renderNavChartLW`, `renderDdChartLW`, `setupChartSync`
- `renderLoadingSkeleton`, `linePath`, `renderLineChart`
- `filterSeriesByRange`, `aggregateOhlc`, `aggregateNav`, `aggregateDrawdown`

#### Scenario: 收益曲线和回撤图表正常渲染
- **WHEN** 回测完成后加载产物
- **THEN** NAV 收益曲线和回撤曲线正常显示在右侧面板

### Requirement: 提取产物加载模块 artifacts.js

系统 SHALL 将产物加载和面板渲染逻辑提取到 `frontend/assets/js/artifacts.js`：
- `loadActiveArtifacts`, `readArtifactWithStatus`, `readArtifactWithFallback`
- `normalizeRunMetaCounters`, `normalizeNavRows`, `computeDrawdownSeries`
- `renderPerfPanel`, `renderExplainPanel`, `renderExecutionPanel`
- `renderFunnelBars`, `renderSymbolPerformancePanel`, `renderTradesList`

#### Scenario: 产物面板正确加载和渲染
- **WHEN** 回测完成后前端加载产物
- **THEN** 绩效摘要、漏斗图、交易明细、执行诊断面板均正确渲染

### Requirement: 提取 UI 控件模块 ui-controls.js

系统 SHALL 将表单和 UI 交互逻辑提取到 `frontend/assets/js/ui-controls.js`：
- `buildConfigDraft`, `applyConfigToUI`, `refreshConfigPanels`
- `setDrawerPanel`, `toggleDrawer`, `switchDockTab`, `setMode`
- `syncExitLinkage`, `updateAtrNote`, `validateConfigDraft`
- `hydrateComposeRows`, `defaultComposeRows`

#### Scenario: 配置表单交互正常
- **WHEN** 用户修改左侧配置面板中的参数
- **THEN** `buildConfigDraft()` 实时生成正确的配置 JSON

### Requirement: 提取 API 客户端模块 api-client.js

系统 SHALL 将 HTTP 请求和状态面板逻辑提取到 `frontend/assets/js/api-client.js`：
- `apiRequestJson` 及其状态管理辅助函数
- `_apiFailureItems`, `_mergeStatusItems`, `_upsertApiStatus`
- `_setApiLoading`, `_setApiSuccess`, `_setApiFailed`
- `setStatusItems`, `toggleStatusPanel`

#### Scenario: API 请求和状态面板正常
- **WHEN** 前端发起任何 API 请求
- **THEN** 请求状态在状态面板中正确显示（加载中/成功/失败）

### Requirement: index.html 更新 script 标签

`frontend/index.html` SHALL 按依赖顺序引入拆分后的 JS 模块：
1. `api-client.js`
2. `ui-controls.js`
3. `charts.js`
4. `artifacts.js`
5. `report.js`
6. `backtest_v2.js`（主文件，包含 `init()`, `bindEvents()`, 全局 `state`）

#### Scenario: 页面加载无 JS 错误
- **WHEN** 浏览器加载 `index.html`
- **THEN** 控制台无 ReferenceError 或 undefined 函数错误，所有功能正常运行

### Requirement: 结果模块拆分必须以单一 DOM ownership 为目标
前端结果相关模块拆分不仅 SHALL 将逻辑拆到独立文件，还 MUST 确保结果区只有一个渲染 owner。多个模块 SHALL NOT 同时渲染或 patch 同一块可见结果 DOM。

#### Scenario: 结果区模块已拆分但仍有双写
- **WHEN** 结果概览、图表、漏斗或交易明细已拆到多个文件
- **THEN** 系统 MUST 指定唯一的结果区 owner
- **THEN** 其他模块仅 MAY 负责数据读取、归一化或 fallback

#### Scenario: legacy helper 保留
- **WHEN** 仍保留 legacy helper 以便回退
- **THEN** 这些 helper SHALL NOT 在结果工作台挂载成功后继续写入可见结果区 DOM
