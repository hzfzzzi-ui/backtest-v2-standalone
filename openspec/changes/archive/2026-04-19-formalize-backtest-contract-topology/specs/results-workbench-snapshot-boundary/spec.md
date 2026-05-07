## ADDED Requirements

### Requirement: results snapshots MUST explain runtime behavior from execution truth first

结果工作台 snapshot MUST 优先使用 `execution_contract` 或 `execution_contract_ref` 解释本次运行行为，不得让 provenance 或旧镜像字段重新成为主真相。

#### Scenario: building a unified combo results snapshot
- **WHEN** 页面壳或 helper 组装 unified combo 的 `ResultsWorkbenchSnapshot`
- **THEN** 运行行为说明 MUST 来自 `execution_contract` 或 `execution_contract_ref`
- **THEN** provenance 只可用于解释合同来源
- **THEN** `comboTruth` 只可用于展示摘要

### Requirement: results snapshots MUST treat legacy source contracts as explanatory fallbacks only

如果结果层仍读取旧 `component_source_contract` 或其它 legacy 镜像，该读取 MUST 被限制为说明或兼容用途。

#### Scenario: reading a legacy combo artifact
- **WHEN** helper 在旧实验结果中找不到独立 `execution_contract.json`
- **THEN** helper MAY 使用 legacy 合同恢复说明信息
- **THEN** helper SHALL NOT 把 legacy source contract 标记为正式执行真相
