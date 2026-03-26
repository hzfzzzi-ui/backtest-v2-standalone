## ADDED Requirements

### Requirement: ETF beta sleeve 研究模式必须支持槽位化选择语义
当 `research_rule_family=broad_based_rotation_template_a0_core_satellite_v2` 时，`cn-etf-beta-sleeve` MUST 支持槽位化选择语义，而不是只输出全池自由排序结果。

该研究模式至少 MUST 暴露：
- `core_slot_selected_symbol`
- `growth_slot_selected_symbol`
- `core_slot_candidate_symbols`
- `growth_slot_candidate_symbols`
- `slot_selection_reason_codes`

#### Scenario: ETF sleeve 运行后可回答每个槽位选了谁
- **WHEN** A0 V2 完成一次调仓或维持持仓
- **THEN** 产物 MUST 能分别回答核心槽位和成长槽位的选择结果

### Requirement: ETF beta sleeve 研究模式必须支持 proxy 替换模式
当 ETF beta sleeve 运行 A0 V2 时，系统 MUST 支持 `proxy_replacement_mode`，并在运行时显式暴露哪些标准 ETF 替换了哪些 proxy。

#### Scenario: 运行中证1000替换 AB
- **WHEN** `proxy_replacement_mode=CSI1000_PROXY_ONLY`
- **THEN** 产物 MUST 明确记录 `159845.SZ` 替换了 `512100.SH`

## MODIFIED Requirements

### Requirement: ETF beta sleeve 必须输出低频、可解释的beta证据
`cn-etf-beta-sleeve` MUST 输出最小可解释证据，包括 `eligible_etfs`、`selected_etfs`、`selection_reason_codes`、`sleeve_budget_used` 和 ETF 资产覆盖摘要。该 sleeve SHALL 优先采用低频调仓与趋势 / 相对强弱框架，而 SHALL NOT 依赖股票 PIT、资金流排序或个股式 ATR breakout 壳。

当研究规则族属于宽基轮动模板时，产物 additionally MUST 暴露：
- `core_slot_selected_symbol`
- `growth_slot_selected_symbol`
- `proxy_replacement_mode`
- `slot_under_deploy_reason_codes`

#### Scenario: ETF beta sleeve 运行后可解释
- **WHEN** ETF beta sleeve 完成一次调仓或拒单决策
- **THEN** 产物 MUST 能回答“为什么是这些 ETF”
- **THEN** 产物 MUST 能回答“为什么当前 ETF sleeve 预算是这个水平”

#### Scenario: 宽基轮动模板可解释槽位空缺
- **WHEN** A0 V2 的某个槽位没有部署任何 ETF
- **THEN** 产物 MUST 暴露该槽位的 under-deploy reason codes
