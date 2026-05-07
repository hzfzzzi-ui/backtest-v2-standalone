# study-definition-runner Specification

## Purpose

定义 `.study.yaml`、`study_run` 和 generated thin script 的正式职责边界，并明确 study 的长期留痕是研究结论，不是并行 baseline。

## Requirements

### Requirement: studies MUST be declared by `.study.yaml`

系统 MUST 使用 `.study.yaml` 作为正式 study 声明。study 定义 MUST 至少包含 `study_id`、`title`、`asset_scope`、`baseline_id`、`hypothesis`、`change_scope`、`variants`、`windows`、`hard_gates` 和 `required_outputs`。

#### Scenario: create a new study

- **WHEN** 用户或系统创建新的正式 study
- **THEN** 系统 MUST 先创建 `.study.yaml`
- **THEN** 缺少必填字段的 study SHALL NOT 进入正式执行

### Requirement: `study_run` MUST be the official study execution entry

系统 MUST 将 `study_run` 作为 study matrix 的唯一正式执行入口。研究脚本 SHALL NOT 再以自定义执行循环充当正式主入口。

#### Scenario: run a study

- **WHEN** 用户执行某个 study
- **THEN** 系统 MUST 通过 `study_run` 调用统一 study runner

### Requirement: generated thin scripts MUST stay thin

`backend/scripts/generated/run_<study_id>.py` MAY 作为按需生成的脚本入口，但 SHALL 只负责转发到 `study_run`。thin script SHALL NOT 内嵌业务循环、config merge、结果判定或 baseline 治理逻辑。

#### Scenario: emit a thin script

- **WHEN** 用户要求脚本式入口
- **THEN** 系统 MAY 生成 thin script
- **THEN** 该脚本 MUST 只做参数转发

### Requirement: studies MUST declare asset scope explicitly

正式 `.study.yaml` MUST 声明 canonical `asset_scope`。系统 SHALL NOT 再通过 baseline 名称或脚本命名推断资产范围。

#### Scenario: load a study definition

- **WHEN** 系统加载正式 study
- **THEN** study MUST 包含 `asset_scope`
- **THEN** 缺少该字段的 study SHALL NOT 进入正式执行

### Requirement: `baseline_id` in a study MUST remain compare-only

study 中声明的 `baseline_id` 只表示 compare 对象，不能表达“把本轮结果升格为 baseline”的隐含意图。

#### Scenario: study points to the active baseline

- **WHEN** 某个 study 以 active baseline 作为 compare 对象
- **THEN** 该 study 只继承 compare 语义
- **THEN** study 结果 SHALL NOT 自动获得 baseline 注册资格

### Requirement: study post-run records MUST collapse to conclusion records

study 运行后的正式长期留痕 MUST 收敛为研究结论记录，而不是继续沉淀为并行 baseline 资产。正式结论记录 MUST 至少包含 `study_id`、`compared_baseline_id`、`verdict`、`summary_short`、`exp_id`、`window_key`、`variant_name` 和 `key_metrics`。

#### Scenario: study_run completes one window/variant

- **WHEN** `study_run` 完成某个 window/variant
- **THEN** 系统 MUST 写入一条 study conclusion 记录
- **THEN** 该记录 MUST 指向 compare baseline 和实验证据

### Requirement: baseline append MUST be compatibility-only and opt-in

study runner SHALL NOT 默认把 study 输出 append 到 baseline ledger、latest champion 或 baseline report。若为了兼容旧工具链保留 append 能力，也 MUST 是显式 opt-in，且不得改变 study 的正式治理身份。

#### Scenario: run a study with default options

- **WHEN** 用户以默认参数执行 `study_run`
- **THEN** 系统 MUST 只写 study 结论和研究输出
- **THEN** 系统 SHALL NOT 默认追加 baseline-style 持久物

#### Scenario: operator explicitly opts into compatibility append

- **WHEN** 操作者显式要求 compatibility append
- **THEN** 系统 MAY 生成兼容型 baseline append 输出
- **THEN** 这些输出 SHALL NOT 被解释为新的 active baseline 或 baseline promotion
