## ADDED Requirements

### Requirement: compiled plan MUST remain a compile snapshot

`compiled_plan.json` MUST 只承担编译快照职责，记录 compile 阶段的解析结果、装配轨迹和计划信息，不得再承担正式执行真相职责。

#### Scenario: writing a new compiled plan artifact
- **WHEN** 系统为新实验写出 `compiled_plan.json`
- **THEN** 该文件 MUST 只描述 compile 结果、组件解析与 assembly trace
- **THEN** 调用方 MUST 通过独立的 `execution_contract.json` 识别正式执行真相

### Requirement: compiled plans MUST separate execution truth from assembly traces

如果编译结果需要同时记录执行合同和来源装配信息，系统 MUST 将两者分层表达，不得继续把来源合同当作可执行输入主源。

#### Scenario: compiling a unified combo run
- **WHEN** compiler 解析 stock / ETF 组件并写出编译结果
- **THEN** `execution_contract` MUST 作为独立正式合同对象存在
- **THEN** assembly/provenance 信息 MUST 通过 `assembly_trace` 或等价辅助对象表达
- **THEN** `component_source_contract.components[*].compile_input.runtime_config` SHALL NOT 继续作为新产物的正式执行输入源

### Requirement: legacy compiled-plan fallbacks MUST be read-only

系统 MAY 为旧实验保留从 `compiled_plan.json` 还原执行合同的兼容逻辑，但该路径 MUST 只用于 legacy 只读回放。

#### Scenario: reading a pre-cutover experiment
- **WHEN** 历史实验目录中不存在 `execution_contract.json`
- **THEN** 调用方 MAY 从 `compiled_plan.json` 还原只读执行合同
- **THEN** 该兼容路径 SHALL NOT 被新实验或新运行链继续当作正式执行合同来源
