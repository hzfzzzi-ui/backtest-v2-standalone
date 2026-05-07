## MODIFIED Requirements

### Requirement: cleanup MUST keep a validated replay anchor before removing unified combo transitional paths
在 unified combo 已经完成 `contract_only` 主路径回放验证后，cleanup MUST 继续推进当前 validated replay anchor 的 source wrapper 与新产物 schema 收口，删除已被正式合同替代的 legacy 来源字段。

#### Scenario: 清理 unified combo legacy 来源字段
- **WHEN** 系统已通过 `A_STOCK_ETF_V1` replay anchor 验证 contract-only 主路径
- **THEN** cleanup MUST 删除不再需要的 `unified_runtime.sleeves`、`combo_components` 与并列 `component_source_mode`
- **THEN** cleanup SHALL NOT 改变该 replay anchor 对应的结果语义
