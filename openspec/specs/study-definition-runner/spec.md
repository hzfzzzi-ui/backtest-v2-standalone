# study-definition-runner Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.
## Requirements
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

### Requirement: study 定义必须显式声明 asset scope
系统 MUST 要求正式 `.study.yaml` 定义声明 canonical `asset_scope`。`study_run` SHALL 透传该字段进入 runtime compile，而 SHALL NOT 继续通过 baseline 或脚本命名推断资产类型。

#### Scenario: 创建新的 study
- **WHEN** 用户或 AI 创建新的正式 study
- **THEN** study 定义 MUST 包含 `asset_scope`
- **THEN** 缺失该字段的 study SHALL NOT 进入正式执行

#### Scenario: generated thin script 运行 study
- **WHEN** generated thin script 调用 `study_run`
- **THEN** thin script MUST 只透传 study 中声明的 asset scope
- **THEN** thin script SHALL NOT 自行注入 A 股默认

### Requirement: baseline 绑定不得代替资产入口声明
系统 SHALL NOT 继续把 `baseline_id` 当作正式资产入口语义。baseline 只用于对照和回归，不得代替 study 的资产范围声明。

#### Scenario: study 绑定 baseline_V10.1
- **WHEN** 某个 study 以 `baseline_V10.1` 作为对照
- **THEN** 该 study 仍 MUST 自己声明 `asset_scope`
- **THEN** 系统 SHALL NOT 仅因为 baseline 属于 A 股就省略资产入口声明

### Requirement: generated thin script 必须成为默认研究脚本入口
系统 MUST 将 `backend/scripts/generated/run_<study_id>.py` 作为 study 的默认脚本入口。顶层手写 `_research.py` wrapper SHALL NOT 再作为并存的正式入口保留。

#### Scenario: 用户需要脚本式入口
- **WHEN** 某个 study 需要被直接脚本执行
- **THEN** 系统 MUST 生成或复用对应的 generated thin script
- **THEN** 该入口 SHALL 通过 `backend.cli study_run` 执行统一 study runner

#### Scenario: 已迁移专题仍保留旧 wrapper
- **WHEN** 某个研究专题已经存在 `.study.yaml` 与 generated thin script
- **THEN** 顶层 `_research.py` wrapper MUST 可以被直接删除
- **THEN** 系统 SHALL NOT 再要求保留双入口

### Requirement: study runner 必须支持批量替代顶层研究定义脚本
系统 MUST 允许批量将顶层研究定义脚本中的矩阵、窗口、baseline、patch 逻辑迁入 `.study.yaml`。迁移完成后，study runner SHALL 成为该批实验的唯一正式执行器。

#### Scenario: 迁移一组 V10 研究脚本
- **WHEN** 系统迁移一组同类型 V10 研究脚本
- **THEN** 每个专题 MUST 拥有对应 `.study.yaml`
- **THEN** 每个专题 MAY 生成 thin script
- **THEN** 顶层研究脚本 SHALL NOT 再承载矩阵定义

