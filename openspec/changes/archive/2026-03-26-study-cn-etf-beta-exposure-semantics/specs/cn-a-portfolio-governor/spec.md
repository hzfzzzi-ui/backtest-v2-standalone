## ADDED Requirements

### Requirement: Governor 必须为 ETF sleeve 输出暴露压缩原因
系统 MUST 为 `cn_etf_beta` 输出可审计的暴露压缩来源，至少覆盖预算上限、slot 限制、绝对过滤与 fallback 触发。

#### Scenario: ETF 暴露被压缩
- **WHEN** `cn_etf_beta` 的实际暴露低于目标暴露
- **THEN** Governor 产物 MUST 输出对应的 `under_deploy_reason_codes`
- **THEN** 原因列表 MUST 能区分预算上限、slot 限制、绝对过滤与 fallback 触发

### Requirement: Governor 必须支持 ETF sleeve 的状态分段目标暴露研究
系统 MUST 允许 `cn_etf_beta` 在不改变 canonical 5-state 真相源的前提下，研究不同状态下的目标暴露映射。

#### Scenario: 按状态定义 ETF 目标暴露
- **WHEN** ETF 暴露语义研究定义了状态分段目标暴露
- **THEN** Governor MUST 接受该映射并输出到产物
- **THEN** canonical 5-state SHALL 仍然是唯一正式状态真相源
