## MODIFIED Requirements

### Requirement: index.html 更新 script 标签
`frontend/index.html` SHALL 在正式 host 之后引入独立的 `runtime-surface.js`，并让所有依赖 shared frontend runtime surface 的脚本都通过该模块获得共享 helper 与 `state` 词法绑定，而不是继续隐式依赖 `backtest_v2.js`。

#### Scenario: shared runtime surface 在主链上先于依赖脚本加载
- **WHEN** 浏览器加载 `index.html`
- **THEN** `desktop-shell/runtime-surface.js` MUST 在依赖 `state`、`byId`、`cloneJson`、asset scope helper 或 results bridge helper 的脚本之前加载
- **THEN** 这些脚本 SHALL NOT 继续以 `backtest_v2.js` 作为 shared runtime surface owner

### Requirement: 旧桌面 bootstrap 必须继续退化为薄壳
系统 MUST 继续收缩 `backtest_v2.js` 的活跃职责。在第二阶段中，跨模块共享的 helper 与 runtime surface MUST 从 `backtest_v2.js` 迁出到正式模块；`backtest_v2.js` 只允许保留 compat shell 专属的页面级 bootstrap、事件接线与过渡逻辑。

#### Scenario: 旧壳不再承接 shared helper surface
- **WHEN** `api-client.js`、`config-draft-core.js`、`config-workspace.js`、`load-orchestration.js`、`history-workspace.js`、`results-workspace.js` 等脚本运行
- **THEN** 它们依赖的 shared helper/runtime function MUST 来自正式模块
- **THEN** `backtest_v2.js` SHALL NOT 再作为这些跨模块共享函数的定义来源
