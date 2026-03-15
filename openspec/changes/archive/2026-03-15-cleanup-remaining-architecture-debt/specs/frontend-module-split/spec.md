## ADDED Requirements

### Requirement: 旧桌面控制器必须继续退化为薄壳
系统 MUST 继续收缩 `backtest_v2.js`、`ui-controls.js` 和 `artifacts.js` 的活跃职责。已经拆出的页面模块 SHALL 成为对应功能的唯一活跃实现，旧文件只允许保留 bootstrap、事件装配和少量桥接逻辑。

#### Scenario: 用户执行配置加载或运行控制
- **WHEN** 桌面研究页触发配置、历史、加载、保存或运行动作
- **THEN** 对应行为 MUST 由 `frontend/assets/js/pages/*` 中的专用模块承担
- **THEN** `backtest_v2.js` 与 `ui-controls.js` SHALL NOT 再保留同一动作的第二套活跃实现

#### Scenario: 旧控制器保留桥接逻辑
- **WHEN** 某段旧控制器暂时仍需存在以完成 bootstrap 或事件接线
- **THEN** 该逻辑 MUST 不直接承担配置编译、结果摘要拼装或重型面板渲染
- **THEN** 旧文件 MUST 维持薄壳角色，避免重新膨胀为全能控制器
