## ADDED Requirements

### Requirement: Component execution contracts MUST include execution overrides
Unified combo 的 `execution_contract.components[*]` SHALL 包含组件进入执行壳所需的执行覆盖参数。若组件运行行为依赖 `enable_multifactor_rank`、`mf_topk`、`mf_rank_gate_mode`、`max_positions` 或同类执行壳参数，这些参数 MUST 写入组件级 `execution_overrides`，不得只存在于语义编译副产物中。

#### Scenario: building a stock component contract with ranking enabled
- **WHEN** compiler 为 stock component 生成 execution contract，且语义配置启用了 final_score/MF 排名
- **THEN** `components.stock_component.execution_overrides.enable_multifactor_rank` MUST 为 `true`
- **THEN** 子腿 runtime MUST 使用该 override 进入执行壳
- **THEN** 运行产物中的 final_score/MF ranking counters MUST 不因 `runtime_config_json` 入口而全部归零

### Requirement: Unified combo runtime MUST execute child sleeves from component execution contracts
Unified combo runtime SHALL 从 `execution_contract.components[*]` 组装子腿请求。组件级 `runtime_config` 与 `execution_overrides` 共同构成子腿执行输入；`component_source_contract` 只能作为 provenance，不得补写或覆盖组件执行输入。

#### Scenario: resolving child sleeve input
- **WHEN** unified combo runtime 同时看到 `execution_contract` 与 `component_source_contract`
- **THEN** 子腿请求 MUST 使用 `execution_contract.components[*].runtime_config`
- **THEN** 子腿请求 MUST 应用 `execution_contract.components[*].execution_overrides`
- **THEN** `component_source_contract.components[*].compile_input` SHALL NOT 覆盖这两类执行参数

### Requirement: Existing contracts without component execution overrides MUST remain compatible
旧 execution contract 若缺少组件级 `execution_overrides`，runtime MAY 以空 overrides 兼容读取，但 SHALL 在新生成的正式合同中写出该字段。

#### Scenario: reading a legacy execution contract
- **WHEN** runtime 读取缺少 `components[*].execution_overrides` 的旧合同
- **THEN** 系统 MAY 使用空 overrides 继续运行
- **THEN** 新写出的 execution contract MUST 补全组件级 `execution_overrides`
