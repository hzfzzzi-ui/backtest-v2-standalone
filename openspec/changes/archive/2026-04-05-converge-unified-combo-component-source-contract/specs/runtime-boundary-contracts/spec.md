## ADDED Requirements

### Requirement: Unified combo MUST publish a formal component source contract alongside transitional provenance
系统 MUST 为 unified combo 发布显式的 `component_source_contract` 元数据对象，用于表达组件来源的正式字段集合、当前来源模式以及是否仍处于过渡阶段。该对象 MUST 与现有 `research_custom_sleeves` 等 provenance 并存，直到替代路径完成验证。

#### Scenario: 编译 unified combo 运行配置
- **WHEN** 后端将 unified runtime wrapper 编译为 unified combo 运行配置
- **THEN** 编译结果 MUST 包含 `component_source_contract`
- **THEN** 该对象 MUST 至少表达 `contract_version`、`source_mode`、`transitional` 与各组件来源摘要

#### Scenario: 产出 unified combo 运行结果
- **WHEN** unified combo 运行完成并写出 `run_meta.json`
- **THEN** 运行产物 MUST 包含与编译阶段一致的 `component_source_contract`
- **THEN** 调用方 SHALL NOT 需要重新解析 legacy provenance 才能识别组件来源合同

### Requirement: Transitional provenance MUST NOT be treated as a shared execution contract
系统 SHALL 将 `research_custom_sleeves`、legacy nested sleeve config 与等效来源信息限制为 unified combo 的 transitional provenance。它们 MUST NOT 被声明为 execution kernel 或共享正式运行边界的输入合同。

#### Scenario: 读取 unified combo source metadata
- **WHEN** 前端、审计层或 cleanup 审计读取 unified combo 的 source metadata
- **THEN** 系统 MAY 同时返回 `research_custom_sleeves` 与 `component_source_contract`
- **THEN** 消费方 MUST 将前者解释为 provenance，将后者解释为正式来源合同
