## MODIFIED Requirements

### Requirement: Results workbench MUST prefer `component_source_contract` over legacy combo source fields
前端结果工作台在解析 unified combo 的组件来源与组合来源模式时，MUST 优先读取 `component_source_contract`。在 `contract_only` 主路径收口完成后，结果工作台 SHALL NOT 再把 `combo_components` 或并列 `component_source_mode` 当作当前运行真相来源。

#### Scenario: 运行产物已进入 contract-only 稳态
- **WHEN** `run_meta.json` 提供 `component_source_contract` 且当前来源模式为 `contract_only`
- **THEN** 前端 MUST 仅以 `component_source_contract` 解释当前来源合同
- **THEN** 前端 SHALL NOT 再依赖 `combo_components` 或旧 `component_source_mode` 字段

### Requirement: Unified combo runtime MUST resolve component compile inputs from `component_source_contract` first
unified combo 的编译与运行服务 MUST 从 `component_source_contract.components[*].compile_input` 解析 stock sleeve 与 ETF sleeve 的运行输入。在 validated replay anchor 已迁到 contract-only 后，系统 SHALL NOT 再消费 legacy `unified_runtime.sleeves[*]`。

#### Scenario: replay anchor 已完成 contract-only 迁移
- **WHEN** unified combo payload 来自当前 validated replay anchor
- **THEN** 编译路径与运行服务 MUST 直接使用 `component_source_contract.components[*].compile_input`
- **THEN** 系统 SHALL NOT 再把 `unified_runtime.sleeves[*]` 作为 fallback
