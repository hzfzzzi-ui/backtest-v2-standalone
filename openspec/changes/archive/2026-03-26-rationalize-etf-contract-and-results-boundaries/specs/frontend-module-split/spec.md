## ADDED Requirements

### Requirement: 旧桌面壳不得再承担结果真相计算
`backtest_v2.js`、`ui-controls.js` 和 `artifacts.js` SHALL NOT 再承担 regime、Governor、research combo 或 ETF sleeve 正式结果真相的计算职责。它们只允许保留 bootstrap、事件桥接、snapshot 推送和兼容提示。

#### Scenario: 渲染结果工作台
- **WHEN** 结果工作台已经基于 snapshot 挂载
- **THEN** 旧桌面壳 SHALL NOT 再计算或重写正式结果语义
- **THEN** 旧桌面壳 MAY 仅负责加载、桥接和空态提示

### Requirement: 旧桌面壳不得保留重复活跃 helper
前端主路径 MUST 禁止在旧桌面壳中继续保留重复定义的活跃 helper 或 owner 冲突函数。若因回退需要保留过渡函数，系统 MUST 明确标记为 legacy shim，并由边界测试阻止其再次成为正式入口。

#### Scenario: 页面壳存在同名活跃函数
- **WHEN** 旧桌面壳中出现同名 helper 的第二份活跃定义
- **THEN** 系统 MUST 将其视为 owner 冲突
- **THEN** 边界测试 MUST 失败

### Requirement: 页面 owner map 必须显式区分 chrome owner 与 results owner
桌面前端 MUST 显式区分页面 chrome owner 与 results owner。chrome owner 只负责顶部条、左 rail、抽屉和页面级交互；results owner 只负责结果工作台的真相消费和结果渲染。

#### Scenario: 页面切换实验或切换资产范围
- **WHEN** 用户切换实验、配置或资产范围
- **THEN** chrome owner MAY 更新页面级控件与导航
- **THEN** results owner MUST 继续作为唯一结果渲染宿主
