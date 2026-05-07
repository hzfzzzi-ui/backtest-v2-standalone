## ADDED Requirements

### Requirement: BUY 订单必须在 planning 阶段满足 fill 等价现金可负担性

系统在生成 BUY 订单时 SHALL 使用与次日 fill 阶段一致的净成本口径判断现金可负担性，而不能只按毛金额或未计成本价格判断。

#### Scenario: planning 阶段按 fill 等价口径判定 BUY 可负担
- **WHEN** execution kernel 为某个 BUY 候选计算订单成本
- **THEN** 系统必须使用与 fill 阶段一致的 `open/slippage/commission` 口径估算净成本
- **THEN** 只有净成本不超过当时 `est_cash` 的订单才允许进入 scheduled orders

#### Scenario: 不可负担 BUY 订单在 planning 阶段按整手裁剪
- **WHEN** 某个 BUY 候选的原始目标数量超出 `est_cash`
- **THEN** 系统必须先按 lot size 计算最大可负担数量
- **THEN** 若最大可负担数量至少为一手，则系统必须生成裁剪后的 BUY 订单而不是整单拒绝

#### Scenario: 裁剪后不足一手的 BUY 候选不得进入 scheduled orders
- **WHEN** 某个 BUY 候选在按 fill 等价净成本和 lot size 裁剪后仍不足一手
- **THEN** 系统必须在 planning 阶段直接拒绝该候选
- **THEN** 拒绝原因必须记录为现金不足，而不是把该订单推迟到次日 fill 再失败

### Requirement: planning 诊断与 fill 诊断必须能区分现金拒绝层级

系统 MUST 能够区分 execution kernel 的 planning 阶段现金拒绝与次日 fill 阶段现金拒绝，避免 `selected_count` 和真实成交能力混为一谈。

#### Scenario: planning 阶段现金拒绝可观测
- **WHEN** BUY 候选在 execution kernel 因现金不足被拒绝
- **THEN** daily diagnostics 与 candidate audit 必须保留该拒绝记录
- **THEN** 拒绝原因必须可与 fill 阶段的 `INSUFFICIENT_CASH` 区分

#### Scenario: scheduled BUY 不得大规模在次日因同一现金口径被拒
- **WHEN** 系统在 planning 阶段已经按 fill 等价净成本放行 BUY 订单
- **THEN** 在没有额外价格跳变或现金状态变化的前提下，该订单不得在次日再次因为同一现金口径被大规模拒绝
