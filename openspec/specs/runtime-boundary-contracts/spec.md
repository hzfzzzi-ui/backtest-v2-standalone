# runtime-boundary-contracts Specification

## Purpose

This spec defines the formal runtime boundary for backtest experiments and unified combo runs.
The formal runtime boundary is `execution_contract`.
`component_source_contract` and replay-anchor metadata belong to assembly/provenance only.
## Requirements
### Requirement: `execution_contract` MUST be the formal runtime boundary

Backtest runtime SHALL treat `execution_contract` as the only formal execution contract.

#### Scenario: a run enters the execution path
- **WHEN** compiler or runtime service builds a runnable payload
- **THEN** it MUST resolve a single `execution_contract`
- **THEN** execution branches MUST depend only on that contract

### Requirement: source and provenance metadata MUST NOT become execution truth

Assembly metadata such as `component_source_contract`, `component_experiments`, `baseline_id`, `study_id`, `window_key`, `variant_name`, and `linked_exp_id` SHALL be treated as provenance or reference metadata only.

#### Scenario: unified combo carries component assembly metadata
- **WHEN** runtime metadata includes `component_source_contract`
- **THEN** the system MAY retain it for provenance and replay explanation
- **THEN** the system MUST NOT treat it as the formal execution contract

### Requirement: execution contracts MUST be pure parameter contracts

`execution_contract` MUST contain only fields that change runtime behavior.
It SHALL NOT inline source-kind or replay-label metadata.

#### Scenario: validating execution contract fields
- **WHEN** a contract includes `baseline_id`, `study_id`, `linked_exp_id`, `source_kind`, `source_mode`, or `runtime_entry_mode`
- **THEN** that payload is not a valid formal `execution_contract`

### Requirement: references MUST be resolved before runtime

If a run is assembled from baseline, study, or replay anchors, those references MUST be resolved into pure runtime parameters before entering execution.

#### Scenario: unified combo is assembled from stock and ETF anchors
- **WHEN** the system receives component references or anchor metadata
- **THEN** it MUST materialize a pure `execution_contract` before stage-pipeline execution
- **THEN** runtime MUST NOT branch on unresolved reference metadata

### Requirement: result consumers MUST separate execution truth from provenance

Results workbench, audits, and combo result surfaces MUST distinguish:
- execution truth: `execution_contract`
- provenance/reference: component assembly metadata and upstream experiment refs
- display truth: view-model fields such as `comboTruth`

#### Scenario: frontend consumes combo artifacts
- **WHEN** artifact metadata provides both execution and provenance objects
- **THEN** frontend consumers MUST use `execution_contract` to explain runtime behavior
- **THEN** they MAY use provenance objects to explain where the contract came from

### Requirement: manifests and run metadata MUST expose execution truth explicitly

Artifacts SHALL expose the execution truth as a dedicated contract object or reference.
Input snapshots and provenance metadata SHALL NOT be presented as parallel execution truths.

#### Scenario: writing new experiment artifacts
- **WHEN** execution writes `manifest.json` and `run_meta.json`
- **THEN** artifacts MUST identify a single `execution_contract`
- **THEN** `input_config`, `resolved_config`, `compiled_plan`, and provenance metadata MUST remain auxiliary

### Requirement: component runtime contracts MUST be scope-pure

组件级执行合同 MUST 只包含当前组件实际执行所需的参数与子树，不得继续携带兄弟组件的 governed 子树、资产池或无关 schema 映射。

#### Scenario: building a stock component execution contract
- **WHEN** compiler 为 unified combo 生成 stock component 的 `runtime_config`
- **THEN** 该 `runtime_config` MUST 只包含 stock 组件执行所需字段
- **THEN** 该对象 SHALL NOT 包含 ETF 组件 governed 子树或 ETF 专属 schema mapping

#### Scenario: building an ETF component execution contract
- **WHEN** compiler 为 unified combo 生成 ETF component 的 `runtime_config`
- **THEN** 该 `runtime_config` MUST 只包含 ETF 组件执行所需字段
- **THEN** 该对象 SHALL NOT 包含 stock 组件 governed 子树或 stock 专属执行子树

### Requirement: runtime fallbacks MUST NOT re-promote provenance into execution truth

运行时 MAY 为旧实验保留 provenance 兼容读取，但新的正式执行分支 MUST 以 `execution_contract` 为唯一优先来源。

#### Scenario: resolving component inputs for a new unified combo run
- **WHEN** 运行时同时看到了 `execution_contract` 与 `component_source_contract`
- **THEN** 运行时 MUST 先使用 `execution_contract`
- **THEN** provenance 字段 SHALL NOT 覆盖、修改或重建执行真相

