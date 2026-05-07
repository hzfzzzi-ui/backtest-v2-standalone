## ADDED Requirements

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
