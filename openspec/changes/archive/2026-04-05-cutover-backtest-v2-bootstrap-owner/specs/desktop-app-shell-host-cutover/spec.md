## MODIFIED Requirements

### Requirement: 新桌面壳正式接管默认宿主入口
系统 SHALL 让新的 `desktop app` host 成为桌面端默认宿主入口，并通过单一 host/bootstrap owner 接管共享 `state` 初始化与页面主启动分发，而不是继续由旧 `backtest_v2.js` 直接持有这些职责。

#### Scenario: 默认宿主入口指向新 host
- **WHEN** 用户打开桌面端首页
- **THEN** 系统 MUST 先由正式 host/bootstrap owner 初始化共享 `state`
- **THEN** 页面主启动 MUST 通过 host 入口分发，而不是 `index.html` 直接调用旧壳的 `init()`

### Requirement: 旧桌面壳只允许作为迁移层
系统 SHALL 将旧 `backtest_v2.js`、旧 bridge 和旧桌面 page controls 定义为迁移层，并为其设置正式退出条件。在 owner cutover 完成后，旧壳 MAY 继续保留 compat helper、bridge 和 legacy init 委托，但 SHALL NOT 再拥有主 bootstrap owner 身份。

#### Scenario: 旧壳不再是正式主路径 owner
- **WHEN** 系统描述桌面端正式主路径
- **THEN** 旧壳组件 MUST 不再被定义为共享 `state` owner 或页面主启动 owner
- **THEN** 旧壳只 MAY 保留兼容层职责，直到后续 helper/runtime 迁移完成
