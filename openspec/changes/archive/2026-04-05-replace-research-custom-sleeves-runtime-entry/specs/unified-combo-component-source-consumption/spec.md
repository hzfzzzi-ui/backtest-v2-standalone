## ADDED Requirements

### Requirement: Results workbench MUST prefer `component_source_contract` over legacy combo source fields
前端结果工作台在解析 unified combo 的组件来源与组合来源模式时，MUST 优先读取 `component_source_contract`。只有在该合同对象缺失时，前端 MAY 回退到 `combo_runtime.component_source_mode`、`research_combo.component_source_mode`、`combo_context.component_source_mode` 或旧 `combo_components`。

#### Scenario: 运行产物同时包含新旧来源字段
- **WHEN** `run_meta.json` 同时包含 `component_source_contract` 与旧 `combo_components` / `component_source_mode`
- **THEN** 前端 MUST 以 `component_source_contract` 作为第一来源
- **THEN** 旧字段 SHALL 仅作为 fallback

### Requirement: Unified combo runtime MUST resolve component compile inputs from `component_source_contract` first
unified combo 的编译与运行服务 MUST 优先从 `component_source_contract.components[*].compile_input` 解析 stock sleeve 与 ETF sleeve 的运行输入。只有在该输入缺失时，系统 MAY 回退到 legacy `unified_runtime.sleeves[*]`。

#### Scenario: 合同对象已包含完整 `compile_input`
- **WHEN** `component_source_contract.components.stock_component.compile_input` 与 `etf_component.compile_input` 都存在
- **THEN** 编译路径与运行服务 MUST 直接使用这些输入
- **THEN** 系统 SHALL NOT 再把 legacy `research_custom_sleeves` 入口当作主消费入口
