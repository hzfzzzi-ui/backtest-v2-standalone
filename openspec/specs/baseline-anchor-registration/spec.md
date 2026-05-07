# baseline-anchor-registration Specification

## Purpose

定义正式 baseline 的注册、法源、状态机和人工 apply 守门规则，确保 baseline 可审计、可回滚、可复核。

## Requirements

### Requirement: baseline registration MUST persist an independent baseline record

系统 MUST 为每个正式 baseline 写出独立的 `outputs/baselines/<baseline_id>/baseline.json` 和配置快照，并同步刷新 `outputs/baselines/index.json`。

#### Scenario: register a new baseline

- **WHEN** 操作者注册一个新的正式 baseline
- **THEN** 系统 MUST 写出 `baseline.json`
- **THEN** 系统 MUST 写出 `baseline_config_snapshot.json` 和 `config.json`
- **THEN** 系统 MUST 更新 `outputs/baselines/index.json`

### Requirement: baseline truth MUST come from `baseline.json.linked_exp_id`

正式 baseline 的 canonical metrics、compare truth 和 audit truth MUST 来自 `baseline.json.linked_exp_id` 对应实验。`index.json`、`latest_champion.json`、human digest 等展示层文件 SHALL NOT 反向充当 baseline 法源。

#### Scenario: linked experiment is available

- **WHEN** baseline 的 `linked_exp_id` 可解析到本地实验目录
- **THEN** 系统 MUST 以该实验的正式产物作为 baseline truth
- **THEN** 若 `index.json` 或 `latest_champion.json` 与其冲突，系统 MUST 将其视为 display-layer conflict，而不是 baseline truth

#### Scenario: linked experiment is missing

- **WHEN** baseline 的 `linked_exp_id` 缺失，或对应实验目录不可解析
- **THEN** 系统 SHALL NOT 将该 baseline 视为 fully reproducible formal baseline
- **THEN** 系统 MUST 要求先补齐 linked experiment 或将其降级为非 active 状态

### Requirement: baselines MUST bind execution contracts explicitly

正式 baseline 除 `linked_exp_id` 外 MUST 显式绑定 `execution_contract_ref`，用于定位正式执行合同。

#### Scenario: write baseline record

- **WHEN** 系统写出或更新 `baseline.json`
- **THEN** baseline MUST 记录 `linked_exp_id`
- **THEN** baseline MUST 记录 `execution_contract_ref`

### Requirement: baseline snapshots MUST NOT redefine baseline truth

baseline 配置快照 MAY 用于 workbench 恢复、说明或 provenance，但调用方 MUST NOT 通过快照重定义 baseline 身份或指标真相。

#### Scenario: load a baseline into the workbench

- **WHEN** 前端或服务层读取 baseline 配置快照
- **THEN** 调用方 MAY 用其恢复配置
- **THEN** 调用方 SHALL NOT 通过该快照替代 `linked_exp_id` 法源

### Requirement: only one active baseline MAY exist for the same effective period

同一 `effective_period` 下最多只能存在一个 `active` baseline。其余 baseline MUST 显式标记为 `archived`、`superseded`、`invalid` 或 `replay_anchor`。

#### Scenario: register a second active baseline for the same effective period

- **WHEN** 某个 `effective_period` 已经存在一个 `active` baseline
- **THEN** 系统 MUST 拒绝注册第二个 `active` baseline
- **THEN** 系统 MUST 要求先降级旧 baseline，或明确结束其生效期

#### Scenario: keep historical baselines for traceability

- **WHEN** 旧 baseline 被新的 active baseline 替代
- **THEN** 系统 MAY 保留其目录和历史报告
- **THEN** 该 baseline MUST 被标记为 `superseded` 或 `archived`

### Requirement: baseline apply MUST be manually confirmed before activation

任何 baseline 切换、重挂或 active apply 前，系统 MUST 先向用户明确报告最终保留 baseline、其 `linked_exp_id`、个股腿绩效、ETF 或组合腿绩效，以及其余 baseline 的降级名单；在用户确认前 SHALL NOT 实施 active baseline 切换。

#### Scenario: candidate baseline is identified but not confirmed

- **WHEN** 系统已经识别出新的候选 baseline
- **THEN** 系统 SHALL NOT 自动切换 active baseline
- **THEN** 系统 MUST 先展示 apply confirmation checklist

#### Scenario: user confirms the apply decision

- **WHEN** 用户明确确认最终保留 baseline 和降级名单
- **THEN** 系统 MAY 执行 active baseline 切换与其余 baseline 降级
