## ADDED Requirements

### Requirement: manifests MUST identify execution truth separately from compile snapshots

新实验产物 MUST 在 `manifest.json` 中显式区分执行真相与编译快照，禁止继续把 `compiled_plan`、`run_meta` 或输入快照视为并列执行真相。

#### Scenario: writing a new experiment manifest
- **WHEN** 系统写出 `manifest.json`
- **THEN** `execution_contract` MUST 作为独立核心 artifact 出现
- **THEN** `compiled_plan`、`input_config`、`resolved_config` SHALL 被标记为辅助快照或编译产物

### Requirement: run metadata MUST remain a runtime fact index

`run_meta.json` MUST 收口为运行事实索引，只保留运行事实、执行合同引用、依赖索引和 provenance。

#### Scenario: writing run metadata for a new experiment
- **WHEN** 系统写出 `run_meta.json`
- **THEN** `execution_contract_ref` MUST 成为正式执行真相定位锚
- **THEN** `provenance` MUST 独立表示来源与装配说明
- **THEN** 结果摘要、视图上下文和执行全文镜像 SHALL NOT 继续作为并列主真相对象

### Requirement: execution mirrors in run metadata MUST be compatibility-only

如果系统在兼容窗口内仍保留 `run_meta.execution_contract` 等全文镜像，它们 MUST 被明确标注为兼容副本，不得取代 `execution_contract_ref`。

#### Scenario: consuming run metadata during the compatibility window
- **WHEN** 调用方在 `run_meta.json` 中同时看到 `execution_contract_ref` 与 `execution_contract`
- **THEN** 调用方 MUST 以 `execution_contract_ref` 和独立 artifact 作为正式执行真相
- **THEN** 全文镜像 SHALL 只被视为兼容副本
