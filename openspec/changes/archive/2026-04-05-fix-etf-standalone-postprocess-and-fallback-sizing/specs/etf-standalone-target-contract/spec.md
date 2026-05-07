## ADDED Requirements

### Requirement: ETF standalone inter-rebalance deploy 必须同时暴露最终目标与增量目标
当 ETF standalone research mainline 在 `BULL`、`TRANS_UP` 或 `RISK_OFF` 下触发 inter-rebalance deploy 时，系统 MUST 同时保留两套不混淆的 target 语义：`final_target_weight` 表示该 symbol 的最终组合目标仓位，`target_weight` 表示当日实际应补的增量 deploy gap。系统 SHALL NOT 再让 emitted BUY signal 只携带单一 target 字段，导致下游把 delta order 误读成最终目标仓位。

#### Scenario: 已有持仓时只补增量 gap
- **WHEN** ETF standalone inter-rebalance deploy 当日某个 selected symbol 已存在正持仓暴露
- **THEN** emitted BUY signal 的 `target_weight` MUST 小于或等于同一 signal 的 `final_target_weight`
- **THEN** 系统 MUST 继续保留该 symbol 的 `final_target_weight`，用于 audit 与 artifact 对齐

#### Scenario: 无既有持仓时增量目标可等于最终目标
- **WHEN** ETF standalone inter-rebalance deploy 当日某个 selected symbol 尚无既有持仓暴露
- **THEN** emitted BUY signal 的 `target_weight` MAY 等于其 `final_target_weight`
- **THEN** 两个字段的语义仍 MUST 明确区分为 delta 与 final

### Requirement: ETF standalone partial fallback fill 必须保持 fallback 标的零原始目标语义
当 ETF standalone research mainline 在 partial fallback fill 场景下追加 fallback 标的，且选中集合中仍存在原始正目标权重标的时，系统 MUST 保持 fallback 标的的零原始目标语义。此时 fallback 标的的 `final_target_weight` 与 `target_weight` SHALL NOT 因为 postprocess 默认值、均分逻辑或 fallback 选中而被压成正数。

#### Scenario: partial fallback 仅压缩原始正目标标的
- **WHEN** 选中集合同时包含原始正目标权重标的与零原始目标 fallback 标的
- **THEN** 系统 MUST 仅在原始正目标标的之间压缩 `live_target`
- **THEN** fallback 标的的 `final_target_weight` 与 `target_weight` MUST 同时保持为 `0.0`

#### Scenario: full fallback replacement 仍可承接目标
- **WHEN** 选中集合中不存在任何原始正目标权重标的，且 standalone mainline 进入 full fallback replacement
- **THEN** fallback 选中集合 MAY 承接 `live_target`
- **THEN** 该场景下 fallback 标的的 `final_target_weight` 与 `target_weight` MUST 继续遵守现有执行合同
