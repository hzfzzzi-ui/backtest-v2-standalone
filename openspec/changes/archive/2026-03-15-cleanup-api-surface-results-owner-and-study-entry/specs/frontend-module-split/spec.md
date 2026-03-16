## ADDED Requirements

### Requirement: ui-controls.js 必须优先抽离配置核心
系统 MUST 优先从 `frontend/assets/js/ui-controls.js` 中抽离配置核心逻辑，包括表单字段归一化、config draft 组装、runtime request 编译和相关主路径校验。`ui-controls.js` 继续存在时 SHALL 只承担控件联动、可见性切换和提示文案。

#### Scenario: 构建运行请求
- **WHEN** 桌面研究页准备发起预览或运行请求
- **THEN** config draft 与 runtime request MUST 由独立配置核心模块生成
- **THEN** `ui-controls.js` SHALL NOT 继续作为唯一配置编译宿主

#### Scenario: 控件联动仍留在旧文件
- **WHEN** 用户切换表单项导致 hint、badge 或 panel 可见性变化
- **THEN** `ui-controls.js` MAY 继续负责这些轻量 UI 行为
- **THEN** 该文件 SHALL NOT 重新膨胀为配置真相宿主

### Requirement: artifacts.js 必须退化为结果消费与展示适配层
系统 MUST 让 `frontend/assets/js/artifacts.js` 仅承担结果消费、格式归一化和展示适配职责。该文件 SHALL NOT 继续承载前端主路径中的 artifact 物理读取与路径兜底逻辑。

#### Scenario: 渲染结果卡片
- **WHEN** 前端渲染 KPI、symbol stats、交易明细或阶段漏斗
- **THEN** `artifacts.js` MUST 基于 canonical result model 进行展示适配
- **THEN** 该文件 SHALL NOT 负责主路径 artifact 文件读取
