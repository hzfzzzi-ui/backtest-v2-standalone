## MODIFIED Requirements

### Requirement: 提取产物加载模块 artifacts.js

系统 SHALL 将产物加载、标准化与结果状态桥接逻辑收口到结果工作台单一路径中：
- `loadActiveArtifacts`, `readArtifactWithStatus`, `readArtifactWithFallback`
- `normalizeRunMetaCounters`, `normalizeNavRows`, `computeDrawdownSeries`
- 结果桥接层所需的标准快照构造逻辑

`artifacts.js` 可以继续保留 legacy 适配职责，但系统 MUST 禁止在多个原生模块中散写结果区 DOM。结果概览、9 阶段漏斗、个股排名、详细交易明细、AI Markdown 报告等结果区面板 SHALL 通过单一结果桥接层进入统一渲染壳，而不是在 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 中重复拼接。

#### Scenario: 产物加载后只生成一份标准结果快照
- **WHEN** 回测完成后前端加载产物
- **THEN** 系统 SHALL 先生成单一规范化结果快照
- **THEN** 结果区各面板 SHALL 基于这份快照渲染，而不是各自重新解释 artifacts

#### Scenario: 结果区 DOM owner 单点化
- **WHEN** 某个结果面板已被纳入结构化结果工作台
- **THEN** 原生脚本 SHALL NOT 再直接拼接该面板 DOM
- **THEN** 该面板 SHALL 只通过统一结果渲染壳更新

### Requirement: index.html 更新 script 标签

`frontend/index.html` SHALL 继续按依赖顺序引入拆分后的 legacy JS 模块：
1. `api-client.js`
2. `ui-controls.js`
3. `charts.js`
4. `artifacts.js`
5. `report.js`
6. `backtest_v2.js`

在此基础上，系统 MUST 为结果工作台预留单独挂载点，并允许在 legacy 模块之后引入结构化结果工作台构建产物。该挂载点 SHALL 只接管结果区，不得要求整页改为 SPA。

#### Scenario: 页面加载时 legacy 与结构化结果壳可共存
- **WHEN** 浏览器加载 `index.html`
- **THEN** legacy 运行/配置模块 SHALL 继续可用
- **THEN** 结果工作台挂载点 SHALL 可加载结构化结果壳，而不影响左侧配置区与顶部命令栏

#### Scenario: 结果工作台构建产物缺失时可回退
- **WHEN** 结构化结果工作台构建产物暂不可用
- **THEN** 页面 SHALL 保持 legacy 结果加载能力，不因缺少前端结果壳资源而整页不可用
