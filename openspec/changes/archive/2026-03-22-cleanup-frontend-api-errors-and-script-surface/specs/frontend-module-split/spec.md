## ADDED Requirements

### Requirement: 已提取的桌面页面模块必须成为唯一活跃实现
系统 MUST 将已经提取到 `frontend/assets/js/pages/*` 的桌面页面职责视为唯一活跃实现。`backtest_v2.js` 和 `ui-controls.js` 中对应职责的旧实现 SHALL NOT 继续作为正式入口。

#### Scenario: 页面已提取配置中心职责
- **WHEN** 配置中心、历史面板、加载控制、保存控制或运行控制已经被提取到独立页面模块
- **THEN** 系统 MUST 由提取后的页面模块承载活跃实现
- **THEN** `backtest_v2.js` 或 `ui-controls.js` 中对应旧实现 SHALL NOT 再以原函数名保留为活跃入口

#### Scenario: 旧控制器仍保留过渡函数
- **WHEN** 旧控制器短期内仍保留过渡函数以便回滚
- **THEN** 这些函数 MUST 明确标记为 legacy shim
- **THEN** 它们 SHALL NOT 在页面初始化流程中继续承担主要控制职责

### Requirement: 桌面前端模块拆分必须伴随静态边界测试
系统 MUST 为桌面前端的每次职责外提提供静态边界测试，验证新模块已经承担活跃职责，旧控制器不再保留同名活跃实现。

#### Scenario: 新增页面模块
- **WHEN** 新增一个 `frontend/assets/js/pages/*` 页面模块
- **THEN** 系统 MUST 添加对应的静态边界测试
- **THEN** 测试 MUST 验证 `index.html` 已挂载新脚本且旧文件中不再存在相同签名的活跃函数

#### Scenario: 保留过渡壳
- **WHEN** 旧文件中仍保留 bootstrap 或 legacy shim
- **THEN** 测试 MAY 允许存在 `_legacy...` 过渡函数
- **THEN** 测试 MUST 阻止这些过渡函数重新回到活跃函数名
