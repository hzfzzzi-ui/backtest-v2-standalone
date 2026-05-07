## ADDED Requirements

### Requirement: Unified combo runtime MUST operate on `component_source_contract` only
系统在 unified combo 当前主运行路径中 MUST 只通过 `component_source_contract` 解析组件来源与组件运行输入。legacy `unified_runtime.sleeves[*]`、`research_custom_sleeves` 与等效 fallback 入口 SHALL NOT 继续参与主运行编译与主运行服务的输入解析。

#### Scenario: 执行 unified combo 编译
- **WHEN** 后端编译 unified combo 运行配置
- **THEN** 系统 MUST 从 `component_source_contract.components[*].compile_input` 解析组件输入
- **THEN** 系统 SHALL NOT 再以 legacy `sleeves[*]` 为主入口

#### Scenario: 执行 unified combo 运行服务
- **WHEN** unified combo 运行服务开始构造 stock sleeve 与 ETF sleeve 子运行
- **THEN** 系统 MUST 直接消费 `component_source_contract.components[*].compile_input`
- **THEN** 系统 SHALL NOT 再回退到 legacy `sleeves[*].semantic_config/runtime_config`
