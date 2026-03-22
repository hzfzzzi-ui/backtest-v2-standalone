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

### Requirement: 旧桌面控制器必须继续退化为薄壳
系统 MUST 继续收缩 `backtest_v2.js`、`ui-controls.js` 和 `artifacts.js` 的活跃职责。已经拆出的页面模块 SHALL 成为对应功能的唯一活跃实现，旧文件只允许保留 bootstrap、事件装配和少量桥接逻辑。

#### Scenario: 用户执行配置加载或运行控制
- **WHEN** 桌面研究页触发配置、历史、加载、保存或运行动作
- **THEN** 对应行为 MUST 由 `frontend/assets/js/pages/*` 中的专用模块承担
- **THEN** `backtest_v2.js` 与 `ui-controls.js` SHALL NOT 再保留同一动作的第二套活跃实现

#### Scenario: 旧控制器保留桥接逻辑
- **WHEN** 某段旧控制器暂时仍需存在以完成 bootstrap 或事件接线
- **THEN** 该逻辑 MUST 不直接承担配置编译、结果摘要拼装或重型面板渲染
- **THEN** 旧文件 MUST 维持薄壳角色，避免重新膨胀为全能控制器

### Requirement: ui-controls.js 必须优先抽离配置核心
系统 MUST 优先从 `frontend/assets/js/ui-controls.js` 中抽离配置核心逻辑，包括表单字段归一化、config draft 组装、runtime request 编译和相关主路径校验。`ui-controls.js` 继续存在时 SHALL 只承担控件联动、可见性切换和提示文案。

#### Scenario: 构建运行请求
- **WHEN** 桌面研究页准备发起预览或运行请求
- **THEN** config draft 与 runtime request MUST 由独立配置核心模块生成
- **THEN** `ui-controls.js` SHALL NOT 继续作为唯一配置编译宿主

#### Scenario: 控件联动仍留在旧文件
- **WHEN** 用户切换表单项导致 hint、badge 或 panel 可见性变化
- **THEN** `ui-controls.js` MAY 继续负责这些轻量 UI 行为
- **THEN** 该文件 SHALL NOT 重新膨胀为配置真相宿主

### Requirement: artifacts.js 必须退化为结果消费与展示适配层
系统 MUST 让 `frontend/assets/js/artifacts.js` 仅承担结果消费、格式归一化和展示适配职责。该文件 SHALL NOT 继续承载前端主路径中的 artifact 物理读取与路径兜底逻辑。

#### Scenario: 渲染结果卡片
- **WHEN** 前端渲染 KPI、symbol stats、交易明细或阶段漏斗
- **THEN** `artifacts.js` MUST 基于 canonical result model 进行展示适配
- **THEN** 该文件 SHALL NOT 负责主路径 artifact 文件读取

### Requirement: 已提取的桌面页面模块必须成为唯一活跃实现
系统 MUST 将已经提取到 `frontend/assets/js/pages/*` 的桌面页面职责视为唯一活跃实现。`backtest_v2.js` 和 `ui-controls.js` 中对应职责的旧实现 SHALL NOT 继续作为正式入口。

#### Scenario: 页面已提取配置中心职责
- **WHEN** 配置中心、历史面板、加载控制、保存控制或运行控制已经被提取到独立页面模块
- **THEN** 系统 MUST 由提取后的页面模块承载活跃实现
- **THEN** `backtest_v2.js` 或 `ui-controls.js` 中对应旧实现 SHALL NOT 再以原函数名保留为活跃入口

#### Scenario: 旧控制器仍保留过渡函数
- **WHEN** 旧控制器短期内仍保留过渡函数以便回滚
- **THEN** 这些函数 MUST 明确标记为 legacy shim
- **THEN** 它们 SHALL NOT 在页面初始化流程中继续承担主要控制职责

### Requirement: 桌面前端模块拆分必须伴随静态边界测试
系统 MUST 为桌面前端的每次职责外提提供静态边界测试，验证新模块已经承担活跃职责，旧控制器不再保留同名活跃实现。

#### Scenario: 新增页面模块
- **WHEN** 新增一个 `frontend/assets/js/pages/*` 页面模块
- **THEN** 系统 MUST 添加对应的静态边界测试
- **THEN** 测试 MUST 验证 `index.html` 已挂载新脚本且旧文件中不再存在相同签名的活跃函数

#### Scenario: 保留过渡壳
- **WHEN** 旧文件中仍保留 bootstrap 或 legacy shim
- **THEN** 测试 MAY 允许存在 `_legacy...` 过渡函数
- **THEN** 测试 MUST 阻止这些过渡函数重新回到活跃函数名

## Synced From close-p0-p1-architecture-gaps

### Requirement: 桌面前端必须维护显式 owner map
系统 MUST 为桌面前端维护显式 owner map，至少区分 `页面壳/bootstrap owner`、`config draft core owner` 和 `results workbench owner`。旧壳文件 SHALL NOT 继续跨越这些 owner 边界吸收新逻辑。

#### Scenario: 结果工作台已挂载
- **WHEN** Vue results workbench 已成功挂载到结果区域
- **THEN** `backtest_v2.js`、`ui-controls.js` 或其他 legacy 壳文件 SHALL NOT 继续写入可见结果 DOM
- **THEN** 这些文件 MAY 保留桥接、状态同步或轻量提示职责

#### Scenario: 桌面页编译运行请求
- **WHEN** 桌面页需要从表单生成 config draft 或 runtime request
- **THEN** 相关编译逻辑 MUST 由独立配置核心模块或页面模块承载
- **THEN** legacy 壳文件 SHALL NOT 重新成为唯一配置真相宿主

### Requirement: 前端 owner 收口必须伴随边界测试
系统 MUST 为桌面前端的 owner 收口提供边界测试，验证新宿主已经承接活跃职责，旧壳只保留 bootstrap 或 shim。

#### Scenario: 新增或调整页面模块
- **WHEN** 某个桌面页面模块被新增或调整为正式宿主
- **THEN** 系统 MUST 增加或更新对应的边界测试
- **THEN** 测试 MUST 证明旧壳未继续保留同名活跃实现

#### Scenario: 保留 legacy shim
- **WHEN** 旧文件中因回退需要仍保留 legacy shim
- **THEN** 这些 shim MUST 被显式标记为过渡逻辑
- **THEN** 边界测试 MUST 阻止其重新回流为正式 owner

