## ADDED Requirements

### Requirement: 生产主路径必须移除 fallback 结果 DOM
系统 MUST 从生产主路径中移除 fallback 结果 DOM。桌面结果区在正常运行下 SHALL 只保留 Vue results workbench 作为唯一可见结果渲染 owner。

#### Scenario: 桌面页正常加载
- **WHEN** 用户正常打开桌面研究页并加载实验结果
- **THEN** 结果区 MUST 仅由 Vue results workbench 渲染
- **THEN** 页面 SHALL NOT 再保留可见的 fallback 结果容器

#### Scenario: 旧脚本尝试更新结果 DOM
- **WHEN** `backtest_v2.js`、`artifacts.js` 或其他旧脚本参与结果刷新
- **THEN** 这些脚本 MUST 只更新 snapshot 或调用 workbench 桥接层
- **THEN** 它们 SHALL NOT 直接写入旧结果面 DOM

### Requirement: desktop-research-page 必须成为唯一结果协调层
系统 MUST 让 `desktop-research-page` 成为桌面结果加载、snapshot 组装与 workbench 推送的唯一协调层。其他旧控制器 SHALL NOT 绕过该层直接接管结果渲染流程。

#### Scenario: 加载某个实验 surface
- **WHEN** 桌面页请求某个实验的主 surface 或 section
- **THEN** `desktop-research-page` MUST 负责组装 `ResultsWorkbenchSnapshot`
- **THEN** Vue workbench MUST 仅消费该 snapshot
