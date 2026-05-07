## MODIFIED Requirements

### Requirement: ETF 独立主线必须输出可执行的 BUY 部署订单

ETF 单腿 `standalone mainline` 的 `BULL / TRANS_UP` 部署路径 SHALL 产生与次日真实成交口径一致的 BUY 订单。`selected_count`、`after_cash_lot_count` 与 execution lineage 的 scheduled/fill 结果 MUST 保持可解释对应，不得继续依赖大批次日必败订单制造假阳性的 deployability。

#### Scenario: BULL standalone deploy BUY 订单在 planning 阶段即满足可负担性
- **WHEN** ETF `BULL` 的 inter-rebalance deploy 路径生成 core 或 fallback BUY 订单
- **THEN** execution kernel 必须按 fill 等价净成本和整手约束裁剪该订单
- **THEN** 不可负担的 BUY 不得继续计入可执行部署结果

#### Scenario: TRANS_UP standalone deploy 不得再由次日现金拒绝主导 under-deploy
- **WHEN** ETF `TRANS_UP` 的 inter-rebalance deploy 路径已生成 BUY 订单
- **THEN** execution lineage 中因 `INSUFFICIENT_CASH` 导致的次日拒绝必须显著低于 planning 修复前的水平
- **THEN** 剩余 under-deploy 必须主要由候选不足、slot 或 state 语义解释，而不是 planning/fill 现金合同断层解释
