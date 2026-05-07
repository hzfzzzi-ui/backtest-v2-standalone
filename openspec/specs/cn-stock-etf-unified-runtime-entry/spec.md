# cn-stock-etf-unified-runtime-entry Specification

## Purpose

定义 unified stock + ETF combo 研究入口在当前主线中的组件装配约束、provenance 元数据约束，以及解析为唯一 `execution_contract` 的入口要求。

## Requirements

### Requirement: Unified combo 研究入口必须消费正式 sleeve anchors

当系统以 `cn_stock_etf_v1` 进入 unified stock + ETF combo 研究入口时，系统 MUST 将：

- stock sleeve 物化为正式 `baseline_V10_1`
- ETF sleeve 物化为正式 `etf/cn_etf_first_wave_core` study 的主窗口 `1626` 中的 `CORE` variant

系统 SHALL NOT 再从 unified workbench template 深拷贝两条 sleeve 并假装它们代表正式组件。

#### Scenario: 编译 unified combo research payload

- **WHEN** 系统编译 `cn_stock_etf_v1` 的 unified runtime payload
- **THEN** stock sleeve 的 semantic config 来自 `baseline_V10_1`
- **THEN** ETF sleeve 的 semantic config 来自 `etf/cn_etf_first_wave_core` 主窗口 `1626` 的 `CORE` variant

### Requirement: Unified combo 必须发布正式的 component_source_contract

系统 MUST 为 unified combo 发布显式的 `component_source_contract` 元数据对象，用于表达组件来源与组件 compile input。
该对象属于 assembly / provenance metadata，不是正式执行合同。

#### Scenario: 编译 unified combo 运行配置

- **WHEN** 后端将 unified runtime wrapper 编译为 unified combo 运行配置
- **THEN** 编译结果 MUST 包含 `component_source_contract`
- **THEN** 该对象至少表达 `contract_version` 与各组件来源摘要
- **THEN** 系统 MUST 另外解析出唯一 `execution_contract` 供真正执行路径使用

#### Scenario: 产出 unified combo 运行结果

- **WHEN** unified combo 运行完成并写出 `run_meta.json`
- **THEN** 运行产物 MAY 包含与编译阶段一致的 `component_source_contract`
- **THEN** 调用方 SHALL 通过该对象识别组件来源说明
- **THEN** 调用方 SHALL 通过 `execution_contract` 或其引用识别正式执行真相

### Requirement: Unified combo 研究入口必须显式声明 research-only 组合元数据

当 unified combo 运行时，系统 MUST 在 `compiled_plan` 与 `run_meta` 中写出研究组合元数据，并继续显式标记其为 `research_combo_only`，而不是正式多 sleeve Governor 真相。

#### Scenario: unified combo 运行完成

- **WHEN** unified combo 完成一次运行并生成 `run_meta.json`
- **THEN** `run_meta` MUST 包含 `research_combo_only=true`
- **THEN** `run_meta` MAY 包含 `component_source_contract` 作为 provenance
- **THEN** `run_meta` MUST 标识唯一 `execution_contract` 或其引用
- **THEN** 系统 SHALL NOT 再并列写出 `combo_components`、旧 `component_source_mode` 或等效来源字段作为当前运行真相
