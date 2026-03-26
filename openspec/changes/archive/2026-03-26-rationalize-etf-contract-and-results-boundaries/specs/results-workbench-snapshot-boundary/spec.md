## ADDED Requirements

### Requirement: research combo 必须由后端提供 canonical truth snapshot
当结果属于 research combo 或其他只读组合锚点时，系统 MUST 在后端生成 canonical truth snapshot 或等价 surface，并作为结果工作台的正式输入。前端 SHALL NOT 再通过组件实验结果在客户端拼装伪 snapshot 作为正式组合真相。

#### Scenario: 加载 research combo 结果
- **WHEN** 用户加载一个 research combo 结果
- **THEN** 页面壳 MUST 从后端读取 canonical combo truth
- **THEN** Vue workbench MUST 基于该 truth 渲染组合页

### Requirement: 前端不得再从 dailyRows 或 legacy 字段反推正式 regime / governor / combo 语义
前端 MUST 禁止从 `dailyRows`、`market_state`、`trade_mode`、组件实验 `run_meta` 或其他 legacy 字段自行反推正式 regime、Governor 或 combo 语义。正式语义 MUST 直接来自 snapshot / surface。

#### Scenario: 渲染 Governed A股或 research combo 结果
- **WHEN** 结果工作台需要显示状态、预算或组合来源
- **THEN** 前端 MUST 读取 snapshot 中的正式字段
- **THEN** 前端 SHALL NOT 通过客户端 helper 自行推导第二份语义

### Requirement: ResultsWorkbenchSnapshot 必须区分 canonical truth 与 display formatting
`ResultsWorkbenchSnapshot` 和 experiment surface MUST 负责提供正式结果真相；前端 helper 只允许做展示级格式化，不得承担真相补全、语义迁移或研究口径 fallback。

#### Scenario: 某字段缺失
- **WHEN** 某个 snapshot 字段缺失或旧实验未提供该字段
- **THEN** 前端 MAY 显示 empty state 或兼容提示
- **THEN** 前端 SHALL NOT 为了“看起来完整”而自行重构 formal truth
