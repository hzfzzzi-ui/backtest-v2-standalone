## ADDED Requirements

### Requirement: 结果工作台 SHALL 以 Vue 3 渐进接管结果区

系统 MUST 在不改变后端 `manifest + artifacts` 契约的前提下，为结果工作台提供 Vue 3 挂载壳。首批接管范围 SHALL 包含结果概览、主图表区、个股排名、9 阶段漏斗、详细交易明细与 AI Markdown 报告；左侧配置区、顶部运行区与历史/加载入口 SHALL 保持现有交互方式。

#### Scenario: baseline 结果工作台通过 Vue 壳加载
- **WHEN** 用户加载 `baseline_V1`
- **THEN** 结果工作台 SHALL 通过 Vue 壳渲染结果概览、图表、个股排名、9 阶段漏斗、交易明细与 AI Markdown 报告
- **THEN** 结果数据 SHALL 继续来自既有 `manifest.json` 与标准 artifacts，而不是新后端接口

### Requirement: 结果状态 SHALL 通过单一桥接层进入 Vue 壳

系统 MUST 提供单一结果桥接层，统一承接当前加载对象、标准产物快照、图表模式、symbol 选择、对比基准开关与 accordion 展开状态。Legacy JS SHALL 只更新桥接状态；Vue 壳 SHALL 只消费桥接状态，不得重新发起一套并行结果请求流。

#### Scenario: legacy JS 加载结果后推送标准快照
- **WHEN** legacy 运行/加载逻辑完成 `manifest` 与 artifacts 读取
- **THEN** 系统 SHALL 向结果桥接层写入单一规范化快照
- **THEN** Vue 壳 SHALL 基于同一快照刷新结果工作台，而不是自行重新拼装另一份状态

#### Scenario: 结果区内部交互只修改桥接状态
- **WHEN** 用户切换图表模式、选择个股、展开漏斗或展开交易明细
- **THEN** 结果工作台 SHALL 只更新桥接层中的结果视图状态
- **THEN** 结果区各组件 SHALL 基于同一状态源同步刷新

### Requirement: 结果区 DOM ownership SHALL 单点化

结果工作台首批接管区域在迁入 Vue 壳后，系统 MUST 明确其 DOM owner 为 Vue 结果壳。Legacy JS SHALL NOT 再直接写入这些区域的 DOM，仅可更新桥接状态或调用图表原语。

#### Scenario: 结果区迁入 Vue 后 legacy 不再散写 DOM
- **WHEN** 某个结果面板已纳入 Vue 壳接管范围
- **THEN** `backtest_v2.js`、`ui-controls.js`、`artifacts.js` SHALL NOT 继续直接拼接或覆盖该面板的 DOM
- **THEN** 该面板的渲染 SHALL 由 Vue 组件负责

### Requirement: 结果工作台 SHALL 保持当前结果口径与 100% 缩放可用性

系统 MUST 保持 baseline_V1 的结果展示口径不变，包括 KPI、9 阶段漏斗计数、个股图绝对收盘价与相对倍率展示、AI Markdown 报告字段，并在浏览器 100% 缩放下保证结果区面板可展开、可滚动、可查看完整内容。

#### Scenario: baseline_V1 在 100% 缩放下可用
- **WHEN** 用户以 100% 浏览器缩放加载 `baseline_V1`
- **THEN** 结果工作台 SHALL 正确显示现有 KPI 与结果面板
- **THEN** 个股排名、9 阶段漏斗、详细交易明细 SHALL 可展开且内容不被父容器压扁

#### Scenario: 个股图展示口径保持不变
- **WHEN** 用户查看个股模式图表
- **THEN** 主轴 SHALL 显示个股绝对收盘价
- **THEN** 与基准对比信息 SHALL 显示相对倍率，而不是把主轴改成倍率轴
