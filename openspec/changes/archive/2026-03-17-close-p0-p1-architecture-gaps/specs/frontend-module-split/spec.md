## ADDED Requirements

### Requirement: 桌面前端必须维护显式 owner map
系统 MUST 为桌面前端维护显式 owner map，至少区分 `页面壳/bootstrap owner`、`config draft core owner` 和 `results workbench owner`。旧壳文件 SHALL NOT 继续跨越这些 owner 边界吸收新逻辑。

#### Scenario: 结果工作台已挂载
- **WHEN** Vue results workbench 已成功挂载到结果区域
- **THEN** `backtest_v2.js`、`ui-controls.js` 或其他 legacy 壳文件 SHALL NOT 继续写入可见结果 DOM
- **THEN** 这些文件 MAY 保留桥接、状态同步或轻量提示职责

#### Scenario: 桌面页编译运行请求
- **WHEN** 桌面页需要从表单生成 config draft 或 runtime request
- **THEN** 相关编译逻辑 MUST 由独立配置核心模块或页面模块承载
- **THEN** legacy 壳文件 SHALL NOT 重新成为唯一配置真相宿主

### Requirement: 前端 owner 收口必须伴随边界测试
系统 MUST 为桌面前端的 owner 收口提供边界测试，验证新宿主已经承接活跃职责，旧壳只保留 bootstrap 或 shim。

#### Scenario: 新增或调整页面模块
- **WHEN** 某个桌面页面模块被新增或调整为正式宿主
- **THEN** 系统 MUST 增加或更新对应的边界测试
- **THEN** 测试 MUST 证明旧壳未继续保留同名活跃实现

#### Scenario: 保留 legacy shim
- **WHEN** 旧文件中因回退需要仍保留 legacy shim
- **THEN** 这些 shim MUST 被显式标记为过渡逻辑
- **THEN** 边界测试 MUST 阻止其重新回流为正式 owner
