## MODIFIED Requirements

### Requirement: 旧桌面壳只允许作为迁移层
系统 SHALL 将旧 `backtest_v2.js`、旧 bridge 和旧桌面 page controls 定义为迁移层。在 host owner cutover 之后，shared runtime surface 也 MUST 从旧壳迁出；旧壳 MAY 继续保留 compat helper、legacy init 委托和页面级桥接逻辑，但 SHALL NOT 再承担 shared runtime owner 身份。

#### Scenario: 旧壳退出 shared runtime owner 身份
- **WHEN** 正式 host 与 runtime surface 模块已经加载完成
- **THEN** 旧壳 MUST 不再定义跨模块共享的 `state` 词法绑定、基础 DOM/helper、asset/runtime source helper 或 results bridge helper
- **THEN** 这些 shared dependency MUST 由正式模块承接
