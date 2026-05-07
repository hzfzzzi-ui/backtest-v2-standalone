## ADDED Requirements

### Requirement: 桌面前端模块拆分以新桌面壳为根
系统 SHALL 在前端模块拆分中以新的 `desktop app shell` 作为根模块，而不是继续围绕旧壳或 `results-workbench` 组织宿主职责。

#### Scenario: 模块根不再是旧壳
- **WHEN** 系统定义桌面前端正式模块根
- **THEN** 根模块 MUST 是新的桌面壳
