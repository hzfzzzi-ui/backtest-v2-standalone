## ADDED Requirements

### Requirement: Validated unified combo replay anchors MUST store component compile inputs inside `component_source_contract`

在 unified combo 已完成 `contract_only` 主路径验证后，validated replay anchor baseline MUST 把组件来源与组件 compile input 固化在 `component_source_contract.components[*].compile_input` 中。`unified_runtime.sleeves[*]` SHALL NOT 继续作为 replay anchor 的正式来源字段。

#### Scenario: 读取 A_STOCK_ETF_V1 replay anchor
- **WHEN** 系统加载 `A_STOCK_ETF_V1` baseline source wrapper
- **THEN** `unified_runtime` MUST 携带 `component_source_contract`
- **THEN** stock / ETF sleeve 的 `semantic_config` MUST 来自 `component_source_contract.components[*].compile_input`
- **THEN** baseline SHALL NOT 再依赖 `unified_runtime.sleeves`

### Requirement: Unified combo result artifacts MUST stop emitting parallel legacy source fields after contract-only stabilization

在 `contract_only` 主路径已经通过 replay anchor 验证后，新生成的 unified combo 运行产物 MUST 不再并列输出 legacy 来源字段。

#### Scenario: 写出 unified combo run_meta
- **WHEN** unified combo 运行完成并写出 `run_meta.json`
- **THEN** 产物 MUST 保留 `component_source_contract`
- **THEN** 产物 SHALL NOT 再写出 `combo_components`
- **THEN** 产物 SHALL NOT 再并列写出 `combo_runtime.component_source_mode`、`research_combo.component_source_mode` 或 `combo_context.component_source_mode`

### Requirement: Unified combo component truth MUST resolve from contract-owned refs instead of legacy run_meta fields

结果 surface、审计层与工作台组件真相 MUST 从 contract-owned 组件引用读取，而不是继续从 legacy run_meta 来源字段读取。

#### Scenario: 构建 combo_truth component snapshot
- **WHEN** backend 为 unified combo 生成 `combo_truth`
- **THEN** 系统 MUST 从 `config.component_experiments` 或等价的 contract-owned runtime refs 解析 component exp_id
- **THEN** 系统 SHALL NOT 再依赖 `run_meta.combo_components`
