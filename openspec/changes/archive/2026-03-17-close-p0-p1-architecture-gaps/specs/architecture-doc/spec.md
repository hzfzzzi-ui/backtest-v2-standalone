## ADDED Requirements

### Requirement: 架构文档必须与当前仓库现实同步
系统 MUST 维护与当前仓库现实一致的架构文档，至少覆盖当前目录树、模块职责、主路径/过渡路径/产物路径边界、正式入口和主要运行链。

#### Scenario: 阅读当前架构文档
- **WHEN** 维护者或 AI 阅读当前架构文档
- **THEN** 文档 MUST 能反映 `backend/api`、`backend/core`、`backend/research`、`frontend`、`research`、`tests` 和 `openspec` 的当前职责
- **THEN** 文档 MUST 明确指出 `backend/scripts` 与旧前端壳文件属于过渡层而非长期主路径

#### Scenario: 正式入口发生调整
- **WHEN** CLI、脚本面或桌面主路径的正式入口发生调整
- **THEN** 架构文档 MUST 同步更新
- **THEN** 文档 SHALL NOT 长期保留与仓库现实冲突的入口说明

### Requirement: 守则引用的协议文档与示例必须实际存在
系统 MUST 让架构守则引用的协议文档和示例目录在仓库中实际存在，并与当前正式产物协议保持一致。

#### Scenario: 检查守则引用
- **WHEN** 守则或架构文档引用 schema 文档、example 目录或 runbook
- **THEN** 这些文件和目录 MUST 在仓库中实际存在
- **THEN** 其内容 MUST 与当前正式产物协议和主线运行方式一致

#### Scenario: 正式产物协议发生调整
- **WHEN** run_meta、manifest、rows 或示例产物协议发生正式调整
- **THEN** 对应 schema 文档和 example 目录 MUST 同步更新
- **THEN** 守则文本 SHALL NOT 再引用缺失或过时的路径
