## Why

当前结果工作台已经收口到稳定的 `manifest + artifacts` 协议，但前端仍主要依赖原生 JS 直接操作 DOM。近期为了修复结果区、漏斗、报告与折叠交互，`artifacts.js`、`backtest_v2.js`、`ui-controls.js` 已出现明显的状态逻辑堆积，继续在同一层面叠功能会让结果展示变得难以维护、难以验证，也不利于后续 AI 分析报告与多实验对比扩展。

现在需要在不改后端回测口径、不重写整页工作台的前提下，为结果工作台建立一个可渐进替换的前端结构壳。这样可以先稳定结果区，再逐步推进 Vue 3 接管，避免把前端结构调整与 baseline 结果风险绑在一起。

## What Changes

- 新增结果工作台 Vue 壳能力：在现有 `frontend/index.html` 中为结果区提供单独挂载点，由 Vue 3 渐进接管结果概览、个股排名、9 阶段漏斗、交易明细、AI Markdown 报告。
- 保留现有左侧配置编辑区、顶部运行区、后端 API 与 artifact 协议；Vue 壳只消费既有 `manifest.json`、`perf.json`、`run_meta.json`、`audit.json`、`reason_codes.csv`、`symbol_performance.*`、`trades` 等结果产物。
- 引入前端结果状态桥接层，把“加载 baseline / experiment、读取 artifact、切换图表、展开折叠面板”的状态统一收口，禁止继续在多个原生脚本里散写结果区 DOM。
- 明确迁移边界：第一阶段不做整页组件化，不改变 baseline_V1 与 `exp_20260308_021045840_cde0` 的展示口径，不改后端回测逻辑，不改公开运行接口。
- 为后续 Vue 迁移保留兼容退路：结果工作台允许 legacy JS 与 Vue 壳并存，直到结果区全部迁入统一组件。

## Capabilities

### New Capabilities
- `results-workbench-vue-shell`: 规范结果工作台的 Vue 3 渐进接管边界、状态桥接方式、挂载点、迁移顺序与兼容要求。

### Modified Capabilities
- `frontend-module-split`: 前端模块化要求从“原生脚本拆分”扩展为“结果工作台通过单一结果桥接层接入 Vue 壳，禁止继续在多个模块中散写结果区 DOM”。

## Impact

- 受影响代码：
  - `frontend/index.html`
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/charts.js`
  - `frontend/assets/js/report.js`
  - 新增前端结构化目录与 Vue 3 结果工作台入口
- 受影响系统：
  - 前端结果工作台状态管理
  - 前端结果渲染方式
  - 前端构建/打包链（引入 Vue 3 渐进接管所需的最小构建支持）
- 不受影响：
  - 后端回测引擎
  - baseline 结果口径
  - `config_json -> experiment_id -> manifest/artifact` 协议
