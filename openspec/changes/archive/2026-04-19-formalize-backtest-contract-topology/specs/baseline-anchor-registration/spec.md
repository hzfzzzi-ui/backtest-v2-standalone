## ADDED Requirements

### Requirement: baselines MUST bind execution contracts explicitly

正式 baseline MUST 不仅绑定 `linked_exp_id`，还必须显式绑定该实验的正式执行合同引用。

#### Scenario: registering or re-linking a baseline

- **WHEN** 系统写出或更新 `outputs/baselines/<baseline_id>/baseline.json`
- **THEN** baseline MUST 记录 `linked_exp_id`
- **THEN** baseline MUST 记录 `execution_contract_ref`
- **THEN** baseline 读取方 SHALL 通过该引用定位正式执行合同

### Requirement: baseline snapshots MUST NOT redefine baseline truth

baseline 配置快照 MAY 服务于编辑器恢复或装配说明，但调用方 MUST NOT 使用快照重新定义 baseline 真相。

#### Scenario: loading a baseline into an editor

- **WHEN** 前端或服务层读取 baseline 的配置快照
- **THEN** 调用方 MAY 使用该快照恢复 workbench 配置或 provenance
- **THEN** 调用方 SHALL NOT 通过快照推断或改写 baseline 身份绑定
