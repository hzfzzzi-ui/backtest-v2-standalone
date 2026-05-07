## ADDED Requirements

### Requirement: config_workspace 拥有独立模块边界
系统 SHALL 在前端模块拆分中为 `config_workspace` 保留独立模块边界，并将其与 `results_workspace`、`run_orchestration`、`desktop_shell` 区分。

#### Scenario: 配置工作区模块边界明确
- **WHEN** 系统定义桌面前端正式模块划分
- **THEN** `config_workspace` MUST 作为独立模块出现
