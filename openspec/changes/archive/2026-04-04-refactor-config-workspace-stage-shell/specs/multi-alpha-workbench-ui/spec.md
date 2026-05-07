## ADDED Requirements

### Requirement: 配置工作区正式收口到 config_workspace
系统 SHALL 将多阶段工作台中的配置区域正式收口到 `config_workspace` 语义，而不是继续围绕旧 `S1-S9 + drawer` 壳扩展。

#### Scenario: 配置区正式语义不再依赖旧壳命名
- **WHEN** 系统描述桌面配置模块
- **THEN** 正式模块语义 MUST 以 `config_workspace` 为准
