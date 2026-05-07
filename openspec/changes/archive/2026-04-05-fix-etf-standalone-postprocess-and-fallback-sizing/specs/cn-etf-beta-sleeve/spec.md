## ADDED Requirements

### Requirement: ETF standalone research mainline 必须在订单元数据中保留 final target contract
当 `cn-etf-beta-sleeve` 以 ETF standalone research mainline 口径运行时，系统 MUST 在 emitted BUY signal、`orders.csv` 与等价 artifact 中保留 `final_target_weight`，用于回答该 symbol 经 postprocess 后的最终目标仓位。该字段 SHALL 与 standalone delta `target_weight` 并存，且 SHALL NOT 被旧的 order sizing 默认值覆盖。

#### Scenario: standalone inter-rebalance deploy 输出双 target 语义
- **WHEN** standalone mainline 触发 inter-rebalance deploy BUY signal
- **THEN** 订单元数据 MUST 同时包含 `final_target_weight` 与 delta `target_weight`
- **THEN** 下游 artifact MUST 能仅依赖这两个字段区分“最终目标”与“本次补仓量”

#### Scenario: monthly rebalance 保持既有 target 语义
- **WHEN** standalone mainline 在 monthly rebalance 路径下生成 BUY signal
- **THEN** 系统 MAY 继续沿用既有 monthly rebalance target 语义
- **THEN** 本轮修复 SHALL NOT 改变非 standalone inter-rebalance 路径的 sizing 合同

## MODIFIED Requirements

### Requirement: ETF partial fallback fill 不得把零原始目标的 fallback 标的压成正 `target_weight`

当 ETF standalone research mainline 在 partial fallback fill 场景下追加 fallback 标的时，系统 MUST 保持原始正目标权重标的的 live target 语义。若选中集合中仍存在原始正目标权重标的，则零原始目标的 fallback 标的 SHALL NOT 获得正的 `target_weight`，且其 `final_target_weight` 也 MUST 保持为 `0.0`。

#### Scenario: partial fill 只压缩原始正目标标的

- **WHEN** ETF standalone research mainline 的选中集合同时包含原始正目标标的与零原始目标 fallback 标的
- **THEN** 系统 MUST 仅在原始正目标标的之间按比例压缩 `live_target`
- **THEN** fallback 标的的 `target_weight` MUST 保持为 `0.0`
- **THEN** fallback 标的的 `final_target_weight` MUST 同时保持为 `0.0`

### Requirement: ETF standalone inter-rebalance deploy 必须输出增量 `target_weight`

当 ETF standalone research mainline 在 `BULL`、`TRANS_UP` 或 `RISK_OFF` 下触发 inter-rebalance deploy 时，系统 MUST 将 emitted BUY signal 的 `target_weight` 解释为“本次应补的增量 deploy gap”，而不是最终组合目标仓位。对于已经存在的 ETF 暴露，系统 SHALL 在 emitted BUY signal 前先扣减当前组合暴露。系统 MUST 同时在同一 signal/订单元数据中保留 `final_target_weight`，用于表达该 symbol 的最终组合目标仓位。

#### Scenario: 已有 defense 暴露时 core buy 只补剩余 gap

- **WHEN** ETF standalone inter-rebalance deploy 当日已有 defense/fallback 暴露，且仍需为 core symbol 补仓
- **THEN** emitted core BUY signal 的 `target_weight` MUST 小于对应 symbol 的 `final_target_weight`
- **THEN** emitted BUY signals 的 `target_weight` 总和 MUST 不超过当日 `standalone_deploy_gap`
- **THEN** emitted BUY signals MUST 继续保留各自 symbol 的 `final_target_weight`

### Requirement: standalone delta target 修复不得改变非 standalone inter-rebalance 路径

本轮 delta target 修复 MUST 仅影响 ETF standalone inter-rebalance deploy。monthly rebalance 与 formal `TRANS_UP redeploy` SHALL 保持既有 `target_weight` 合同不变。若系统为这些路径补充 `final_target_weight`，该字段 MUST 仅作为 audit/diagnostics 辅助字段，而 SHALL NOT 改写既有 sizing 口径。

#### Scenario: formal TRANS_UP redeploy 保持既有合同

- **WHEN** formal ETF `TRANS_UP redeploy` 生成 BUY signal
- **THEN** 系统 MUST 继续使用既有 redeploy delta 口径
- **THEN** 本轮 standalone delta target 修复 SHALL NOT 改变该路径的 `target_weight`
- **THEN** 若存在 `final_target_weight`，其 SHALL NOT 改变该路径的 order sizing 结果
