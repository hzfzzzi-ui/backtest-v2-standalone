## MODIFIED Requirements

### Requirement: Unified combo 研究入口必须消费正式 sleeve anchors
当系统以 `cn_stock_etf_v1` 进入 unified stock + ETF combo 正式主线入口时，系统 MUST 将：

- stock sleeve 物化为正式 `baseline_V10.1`
- ETF sleeve 物化为通过 formal alignment 的 `formal ETF stabilizer` compile input
- 该 ETF compile input MUST 显式绑定 `formal_etf_pool_v1`

系统 SHALL NOT 再从 unified workbench template 深拷贝 ETF 研究态输入并将其冒充正式组件来源。

#### Scenario: 编译 unified combo formal payload
- **WHEN** 系统编译 `cn_stock_etf_v1` 的 unified combo 正式运行配置
- **THEN** stock sleeve 的 semantic config MUST 来自 `baseline_V10.1`
- **THEN** ETF sleeve 的 semantic config MUST 来自通过 formal alignment 的 formal ETF stabilizer 输入
- **THEN** ETF sleeve MUST 显式绑定 `formal_etf_pool_v1`

### Requirement: Unified combo 必须发布正式的 component_source_contract
系统 MUST 为 unified combo 发布显式的 `component_source_contract` 元数据对象，用于表达组件来源、运行入口模式、组件身份与 formal pool 版本。

#### Scenario: 组合运行产物发布 formal component truth
- **WHEN** unified combo 运行完成并写出 `run_meta.json`
- **THEN** `component_source_contract` MUST 标明 stock sleeve 与 ETF sleeve 的 formal 身份
- **THEN** ETF component MUST 标明其 `source_entry_type`、`formal_alignment_status` 与 `formal_etf_pool_version`
- **THEN** 调用方 SHALL 通过该对象识别组件是否可晋升主线

## REMOVED Requirements

### Requirement: Unified combo 研究入口必须显式声明 research-only 组合元数据
**Reason**: 本次 change 的目标是把 `stock + ETF` 组合升级为新的正式主线，组合元数据不再以 `research_combo_only` 作为主真相。
**Migration**: 将组合主元数据切换为 formal mainline 组合合同；研究态字段继续保留在 diagnostics / internal audit，不再作为 formal output contract 的主字段。

## ADDED Requirements

### Requirement: Unified combo formal mainline metadata MUST exclude research-only truth markers
当 unified combo 作为正式主线运行时，formal output contract MUST 使用 formal mainline 语义，不得再把 `research_combo_only`、research-only component mode 或 research-only source label 当作主真相。

#### Scenario: formal combo emits top-level metadata
- **WHEN** formal unified combo 写出 `run_meta.json` 与 `audit.json`
- **THEN** formal output MUST 使用 formal mainline 组合身份字段
- **THEN** research-only truth markers SHALL NOT 出现在 formal top-level truth surface
