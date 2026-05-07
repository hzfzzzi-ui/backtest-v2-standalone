## MODIFIED Requirements

### Requirement: 前端模块拆分 MUST 围绕新 desktop app 收口
系统 MUST 围绕新 `desktop app` 拆分前端模块。旧桌面壳、旧 bridge、旧页面控制模块仅可作为迁移期兼容层存在。

#### Scenario: 标记旧壳文件定位
- **WHEN** 系统继续维护 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 或 `desktop-*.js`
- **THEN** 这些文件 MUST 被视为过渡层
- **THEN** 新功能 SHALL NOT 再以这些文件作为长期正式宿主入口
