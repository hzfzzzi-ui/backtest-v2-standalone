## ADDED Requirements

### Requirement: 系统必须以 study 定义驱动实验矩阵
系统 MUST 使用 `.study.yaml` 作为实验矩阵的正式声明式定义。study 定义 MUST 至少包含 `study_id`、`title`、`baseline_id`、`hypothesis`、`change_scope`、`variants`、`windows`、`hard_gates` 和 `required_outputs`。

#### Scenario: 创建一个新的研究专题
- **WHEN** 用户或 AI 发起一个新的研究专题
- **THEN** 系统 MUST 先创建 `.study.yaml`
- **THEN** 该定义 MUST 声明本轮只改什么、如何对照和必须产出什么

#### Scenario: 缺少必要字段的 study
- **WHEN** study 定义缺少必填字段
- **THEN** 系统 SHALL NOT 允许其进入正式执行
- **THEN** 系统 MUST 返回缺失字段说明

### Requirement: study_run 必须成为实验矩阵唯一正式执行器
系统 MUST 将 `study_run` 定义为所有实验矩阵的唯一正式执行器。每个研究专题 SHALL NOT 再拥有自定义执行循环脚本作为正式主入口。

#### Scenario: 运行一个研究矩阵
- **WHEN** 用户执行某个 study
- **THEN** 系统 MUST 通过 `study_run` 调用统一的 study runner
- **THEN** 实验矩阵执行 SHALL 复用统一的总线与产物协议

#### Scenario: 旧研究脚本尝试自带执行循环
- **WHEN** 某个研究脚本仍包含自定义实验循环并尝试作为正式入口
- **THEN** 系统 MUST 将其判定为待迁移旧入口
- **THEN** 该专题 MUST 迁移为 `.study.yaml + study_run`

### Requirement: generated thin script 必须是按需生成的薄入口
系统 MUST 将 `backend/scripts/generated/run_<study_id>.py` 限制为按需生成的薄入口壳。该脚本 SHALL 只负责指定 study、转发少量参数并调用 `study_run`。

#### Scenario: 用户明确需要脚本入口
- **WHEN** 用户要求为某个 active study 提供直接脚本入口
- **THEN** 系统 MAY 生成对应的 thin script
- **THEN** 该脚本 SHALL NOT 内嵌实验业务逻辑

#### Scenario: thin script 试图承载业务逻辑
- **WHEN** thin script 需要自己做 config merge、实验循环或结果判定
- **THEN** 系统 MUST 将其判定为越界
- **THEN** 相关逻辑 MUST 回迁到 study runner 或 service
