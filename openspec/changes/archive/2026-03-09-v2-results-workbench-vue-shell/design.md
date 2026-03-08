## Context

当前前端已经完成一次“归档前压平原生 JS”收口：结果区的 `results_dir` 表面已清理，`artifacts.js` 也回到了单一 active 实现链。但结果工作台仍由原生脚本直接操作 DOM，状态在 `backtest_v2.js`、`ui-controls.js`、`artifacts.js`、`charts.js`、`report.js` 之间分散流动。近期围绕 baseline / experiment 双加载、9 阶段漏斗、AI Markdown 报告、折叠面板、100% 缩放布局所做的修复，已经证明这种结构在继续演化时很容易出现状态漂移和重复逻辑。

另一方面，后端已经稳定收敛到 `config_json -> experiment_id -> manifest + artifacts` 契约，`baseline_V1` 与 `exp_20260308_021045840_cde0` 也已成为当前主线的稳定验收样本。这使得前端可以在不改后端协议的前提下，先对“结果工作台”做结构化接管。

约束条件：

- 不改回测引擎与 baseline 收益口径。
- 不改公开运行接口。
- 不做整页 SPA 重写。
- 左侧配置编辑区、顶部运行区、历史/加载入口继续保持现有交互。

## Goals / Non-Goals

**Goals:**

- 为结果工作台建立 Vue 3 渐进接管壳，只接管结果展示相关区域。
- 建立单一结果状态桥接层，统一承接 `baseline / experiment / manifest / artifacts / chart mode / accordion state`。
- 保持现有 artifact 协议不变，Vue 壳只消费既有标准产物。
- 为后续结果区组件化提供稳定边界，避免继续在多个原生脚本中散写结果区 DOM。
- 保持 baseline_V1 在 100% 缩放下的可用性与展示口径。

**Non-Goals:**

- 不改左侧 9-stage 配置编辑区的渲染技术栈。
- 不把整页一次性改成 Vue SPA。
- 不调整后端回测口径、reason code 口径、artifact schema。
- 不引入新的实验运行入口、结果读取入口或新的后端 API。
- 不在本 change 中完成全量 TypeScript 化。

## Decisions

### 决策 1：只接管结果工作台，不重写整页

结果工作台的首批 Vue 接管范围固定为：

- 运行概览 / KPI 摘要
- 主图表区
- 个股排名
- 9 阶段漏斗
- 详细交易明细
- AI Markdown 报告

左侧配置区、顶部命令栏、历史/加载入口暂留在原生 JS 层。

原因：

- 结果区是当前状态最复杂、迭代最频繁、最容易出现重复 DOM 逻辑的区域。
- 左侧配置区仍承载大量控件联动，和结果区一起迁移会把风险扩大。
- 先把最复杂的结果表面收住，才能为后续全页组件化建立边界。

备选方案：

- 整页一次性 Vue 化：迁移面过大，难以和 baseline 验收拆分，不采用。
- 继续维持原生 JS：短期可行，长期维护成本过高，不采用。

### 决策 2：引入单一结果桥接层，禁止结果区跨模块散写 DOM

新增结果桥接层，作为 legacy JS 与 Vue 壳之间的唯一结果状态入口。该桥接层负责：

- 维护当前加载对象：`load_kind / load_id / exp_id / baseline_id`
- 维护当前 artifact 快照：`manifest / perf / run_meta / audit / reason_codes / symbol_performance / trades / report_md`
- 维护当前结果视图状态：图表模式、symbol 选择、是否对比基准、accordion 展开状态
- 向 Vue 壳推送规范化快照

Legacy JS 仍负责：

- 用户点击运行/加载/保存 baseline
- 发起 API 请求
- 处理运行队列、状态中心、左侧表单

Vue 壳负责：

- 结果工作台 UI 渲染
- 结果区内部交互

原因：

- 结果状态必须先单点收口，否则 Vue 组件只会变成另一层 DOM 散写器。
- 统一桥接层后，legacy 与 Vue 可以短期共存，降低迁移风险。

备选方案：

- 让 Vue 直接重新发起所有 artifact API：会复制 legacy 逻辑并制造两套状态源，不采用。
- 继续在 `artifacts.js` 中直接渲染所有结果区 DOM：无法解决结构问题，不采用。

### 决策 3：采用 Vue 3 + Vite，但只为结果工作台引入最小构建链

前端结构化阶段引入 Vue 3 与最小 Vite 构建链。新目录建议：

- `frontend/app/results-workbench/`：Vue 壳源码
- `frontend/app/results-workbench/components/`：结果区组件
- `frontend/app/results-workbench/store/`：结果桥接适配
- `frontend/assets/dist/`：构建产物

`frontend/index.html` 保持现有结构，只增加结果工作台挂载点与构建产物引用。

原因：

- 结果工作台需要组件边界与状态管理，原生多文件脚本已不够稳。
- Vue 3 更适合在现有 HTML-first 页面里做渐进接管。
- Vite 只服务结果工作台，不必一次性引入全页工程化。

备选方案：

- React：同样可行，但对当前 HTML-first 页面渐进接管成本更高，本 change 不选。
- CDN 直引 Vue ESM：构建和资源版本控制不稳，不采用。

### 决策 4：图表原语保留在 charts.js，先通过 Vue 包装接管

`charts.js` 中与 LightweightCharts 相关的绘制原语保留，Vue 图表组件只负责：

- 生命周期挂载/销毁
- 传入规范化 series
- 管理图表模式切换
- 呈现 badge / footer / tooltip 文案

原因：

- 图表底层逻辑已稳定，并且和 baseline 呈现直接相关。
- 先包装再替换，比直接重写图表实现更安全。

备选方案：

- 在 Vue 内重写所有图表原语：风险过大，不采用。

### 决策 5：结果工作台以 baseline_V1 为首个固定验收样本

前端结构化每一步都以：

- `baseline_V1`
- 关联实验 `exp_20260308_021045840_cde0`

作为首个固定验收样本。

要求至少验证：

- 结果概览 KPI 不漂移
- 9 阶段漏斗计数口径不漂移
- 个股图绝对收盘价/相对倍率展示不漂移
- AI Markdown 报告字段完整
- 100% 缩放下结果区可展开、可滚动

原因：

- 结果工作台结构重构不该改变 baseline 展示口径。
- 必须把 UI 验收和回测结果验收分离。

## Risks / Trade-offs

- [Legacy JS 与 Vue 双栈共存期状态漂移] → 通过单一结果桥接层约束数据流，Vue 不直接重发 artifact 请求。
- [引入构建链增加前端发布复杂度] → 只为结果工作台引入 Vite，保留现有静态页面服务模型。
- [图表与 Vue 生命周期集成导致显示回归] → 保留 `charts.js` 原语，先包装后替换，并以 baseline_V1 固定验收。
- [结果区组件化后仍被 legacy 逻辑偷偷写 DOM] → 在规范中明确结果区 DOM owner 为 Vue 壳，legacy JS 只写桥接状态。
- [100% 缩放下布局再次挤压] → 把结果区容器高度、滚动层、accordion 行为纳入组件化验收基线。

## Migration Plan

1. 新增结果工作台结构化 change，不修改后端与 artifact 契约。
2. 在前端中加入 Vue 3 + Vite 最小构建链与结果区挂载点。
3. 新增结果桥接层，并让 legacy JS 只负责加载结果与推送快照。
4. 首批迁移结果概览、个股排名、9 阶段漏斗、详细交易明细、AI Markdown 报告。
5. 图表区通过 Vue 包装调用现有 `charts.js` 原语。
6. 完成 baseline_V1 的前端 smoke 验证后，再考虑扩大 Vue 接管范围。

回滚策略：

- 挂载点保留 legacy 结果区 fallback。
- 结果桥接层保留旧渲染入口，必要时可切回原生结果区渲染。
- 不涉及后端协议变更，因此回滚仅限前端静态资源。

## Open Questions

- 初版 Vue 壳是否只使用 JavaScript，还是在第二阶段引入 TypeScript。
- 构建产物是否直接提交到仓库，还是由本地/容器构建步骤生成。
- 图表区是否在第一阶段就迁入 Vue 包装，还是先让 Vue 只接管非图表结果面板。
