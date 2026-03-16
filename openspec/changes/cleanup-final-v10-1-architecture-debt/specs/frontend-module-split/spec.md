## MODIFIED Requirements

### Requirement: 旧桌面控制器必须继续退化为薄壳
系统 MUST 持续收缩 `backtest_v2.js`、`ui-controls.js` 和 `artifacts.js` 的活跃职责。已拆出的页面模块和状态模块 SHALL 成为对应功能的唯一正式实现；旧文件只允许保留 bootstrap、桥接和极少量事件装配。

#### Scenario: 用户执行配置加载或运行控制
- **WHEN** 桌面研究页触发配置、历史、加载、保存或运行动作
- **THEN** 对应行为 MUST 由 `frontend/assets/js/pages/*` 或独立状态模块承担
- **THEN** 旧控制器 SHALL NOT 再保留第二套活跃实现

#### Scenario: 旧控制器继续增长
- **WHEN** 新功能需要接入桌面研究页
- **THEN** 新逻辑 MUST 优先进入 `pages/`、`state/`、`results-workbench/` 或专用 helper
- **THEN** `backtest_v2.js`、`ui-controls.js`、`artifacts.js` SHALL NOT 继续长胖

### Requirement: artifacts.js 必须退化为结果消费与展示适配层
系统 MUST 让 `frontend/assets/js/artifacts.js` 只承担结果消费、canonical model 归一化和展示适配职责。该文件 SHALL NOT 再承载主路径中的 artifact 读取、物理路径兜底和运行真相决策。

#### Scenario: 渲染结果卡片
- **WHEN** 前端渲染 KPI、symbol stats、交易明细或阶段漏斗
- **THEN** `artifacts.js` MUST 基于 canonical result model 做展示适配
- **THEN** 该文件 SHALL NOT 再决定去哪里读取底层 artifact

#### Scenario: 处理异常结果
- **WHEN** 某个 section 缺失或 payload 不完整
- **THEN** `artifacts.js` MAY 做展示级降级
- **THEN** 该降级 SHALL NOT 变成物理 artifact 路径 fallback

### Requirement: ui-controls.js 必须只保留控件联动与展示提示
系统 MUST 让 `frontend/assets/js/ui-controls.js` 只保留控件联动、显示提示和轻量 UI 行为。配置草稿构建、runtime request 编译和主真相同步 MUST 迁入独立模块。

#### Scenario: 用户切换控件
- **WHEN** 用户切换某个控件导致 hint、badge 或 panel 可见性变化
- **THEN** `ui-controls.js` MAY 处理这些 UI 行为
- **THEN** 它 SHALL NOT 同时承担完整配置编译

#### Scenario: 页面准备发起运行
- **WHEN** 页面准备发起 preview 或 run 请求
- **THEN** request payload MUST 由独立配置核心生成
- **THEN** `ui-controls.js` SHALL NOT 再作为唯一配置真相宿主

