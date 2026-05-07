# baseline-snapshot-topology Specification

## Purpose
TBD - created by archiving change formalize-backtest-contract-topology. Update Purpose after archive.
## Requirements
### Requirement: baseline identity MUST be independent from baseline config snapshots

系统 MUST 将 baseline 身份绑定对象与 baseline 配置快照对象分开治理。`baseline.json` SHALL 只负责 baseline 身份、绑定关系和正式执行合同定位，不得继续内联装配或组件来源配置。

#### Scenario: reading a baseline identity object
- **WHEN** 系统读取 `outputs/baselines/<baseline_id>/baseline.json`
- **THEN** 该对象 MUST 只包含 baseline 身份字段、`linked_exp_id`、`execution_contract_ref`、状态摘要与配置哈希
- **THEN** 该对象 SHALL NOT 包含 `component_source_contract`、`compile_input`、`semantic_config` 或 `runtime_config`

### Requirement: baseline config snapshots MUST be explicit auxiliary artifacts

系统 MUST 为 baseline 配置快照提供独立的辅助 artifact，并将其标记为装配/编辑快照，而不是 baseline 真相。

#### Scenario: persisting a baseline config snapshot
- **WHEN** 系统写出 baseline 目录中的配置快照
- **THEN** 系统 MUST 写出 `baseline_config_snapshot.json` 作为正式 snapshot artifact
- **THEN** snapshot MAY 包含 `workbench_config`、`component_source_contract` 与编辑恢复所需字段
- **THEN** snapshot SHALL NOT 被任何运行路径当作正式执行合同

### Requirement: baseline indexes MUST remain list caches only

`outputs/baselines/index.json` MUST 只承担列表缓存与摘要职责，不得参与执行真相推导。

#### Scenario: consuming the baseline index
- **WHEN** 前端或服务层读取 `outputs/baselines/index.json`
- **THEN** 调用方 MUST 将其视为列表缓存
- **THEN** 调用方 SHALL 通过 `baseline.json` 与 `execution_contract_ref` 获取正式绑定信息

### Requirement: legacy baseline config aliases MUST remain compatibility-only

兼容窗口内允许保留 `outputs/baselines/<baseline_id>/config.json` 作为 legacy alias，但其职责 MUST 与 `baseline_config_snapshot.json` 完全一致。

#### Scenario: reading a legacy baseline config alias
- **WHEN** 某调用方仍读取 `outputs/baselines/<baseline_id>/config.json`
- **THEN** 系统 MAY 返回与 `baseline_config_snapshot.json` 等价的快照内容
- **THEN** 调用方 SHALL NOT 将该文件视为 baseline 身份或执行真相

