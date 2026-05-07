## MODIFIED Requirements

### Requirement: index.html 更新 script 标签
`frontend/index.html` SHALL 按依赖顺序引入当前正式主链所需的 JS 模块，并显式引入新的 host/bootstrap owner。主装载链必须包含：
1. state 工厂脚本
2. `desktop-shell/state.js`
3. `desktop-shell/host.js`
4. `desktop-shell/bootstrap.js`
5. 其余 `desktop-shell/*` 工作区与 orchestration 模块
6. `backtest_v2.js`（迁移期 compat shell，不再承担主 bootstrap owner 身份）

#### Scenario: 页面加载时主启动 owner 明确
- **WHEN** 浏览器加载 `index.html`
- **THEN** `desktop-shell/host.js` MUST 在 `backtest_v2.js` 之前装配共享 `state`
- **THEN** DOM ready 时页面 MUST 调用 host 入口，而不是直接调用旧壳暴露的 `init()`

### Requirement: 旧桌面 bootstrap 必须继续退化为薄壳
系统 MUST 继续收缩 `backtest_v2.js` 的活跃职责。`desktop-shell/config-workspace.js`、`desktop-shell/results-workspace.js`、`desktop-shell/history-workspace.js` 和 `desktop-shell/*-orchestration.js` 应继续承担对应功能的活跃实现；owner cutover 完成后，`backtest_v2.js` 只允许保留 compat helper、legacy init 委托和轻量桥接逻辑。

#### Scenario: 旧壳不再覆盖 host 创建的 state
- **WHEN** 页面先由 host 创建共享 `state`，随后加载 `backtest_v2.js`
- **THEN** `backtest_v2.js` MUST 复用现有共享状态
- **THEN** 它 SHALL NOT 重新覆盖 host 创建的 `window.state` 与 `window.__WB_STATE__`

### Requirement: 桌面前端模块拆分必须以新桌面壳为根
系统 SHALL 在前端模块拆分中以新的 `desktop app` host 作为根模块，而不是继续围绕旧壳组织宿主职责。前端 harness 与边界测试 MUST 跟随这一主装载链。

#### Scenario: 前端 harness 跟随正式主装载链
- **WHEN** 前端测试 harness 初始化桌面工作台上下文
- **THEN** harness MUST 先加载 host/bootstrap owner，再加载 `backtest_v2.js` 与其余模块
- **THEN** harness SHALL NOT 继续把 `backtest_v2.js` 当成唯一宿主入口
