## ADDED Requirements

### Requirement: ARCHITECTURE.md 架构文档
项目根目录 SHALL 包含 `ARCHITECTURE.md` 文件，描述项目整体架构、目录结构、模块职责和依赖关系。

#### Scenario: 文档包含目录结构图
- **WHEN** 阅读 ARCHITECTURE.md
- **THEN** SHALL 包含完整的项目目录树形图，标注每个顶层目录的用途

#### Scenario: 文档包含模块职责说明
- **WHEN** 阅读 ARCHITECTURE.md
- **THEN** SHALL 包含 backend 各子模块（api, core, configs, scripts）的职责说明

#### Scenario: 文档包含启动方式
- **WHEN** 阅读 ARCHITECTURE.md
- **THEN** SHALL 包含本地开发和 Docker 两种启动方式的说明

#### Scenario: 文档包含前后端交互说明
- **WHEN** 阅读 ARCHITECTURE.md
- **THEN** SHALL 描述前端如何通过 API 与后端交互，列出主要 API 端点
