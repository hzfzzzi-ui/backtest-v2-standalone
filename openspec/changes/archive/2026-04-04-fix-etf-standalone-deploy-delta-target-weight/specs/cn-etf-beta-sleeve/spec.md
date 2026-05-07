## ADDED Requirements

### Requirement: ETF standalone inter-rebalance deploy 必须输出增量 `target_weight`

当 ETF standalone research mainline 在 `BULL`、`TRANS_UP` 或 `RISK_OFF` 下触发 inter-rebalance deploy 时，系统 MUST 将 emitted BUY signal 的 `target_weight` 解释为“本次应补的增量 deploy gap”，而不是最终组合目标仓位。对于已经存在的 ETF 暴露，系统 SHALL 在 emitted BUY signal 前先扣减当前组合暴露。

#### Scenario: 已有 defense 暴露时 core buy 只补剩余 gap

- **WHEN** ETF standalone inter-rebalance deploy 当日已有 defense/fallback 暴露，且仍需为 core symbol 补仓
- **THEN** emitted core BUY signal 的 `target_weight` MUST 小于对应 symbol 的最终目标仓位
- **THEN** emitted BUY signals 的 `target_weight` 总和 MUST 不超过当日 `standalone_deploy_gap`

### Requirement: standalone delta target 修复不得改变非 standalone inter-rebalance 路径

本轮 delta target 修复 MUST 仅影响 ETF standalone inter-rebalance deploy。monthly rebalance 与 formal `TRANS_UP redeploy` SHALL 保持既有 `target_weight` 合同不变。

#### Scenario: formal TRANS_UP redeploy 保持既有合同

- **WHEN** formal ETF `TRANS_UP redeploy` 生成 BUY signal
- **THEN** 系统 MUST 继续使用既有 redeploy delta 口径
- **THEN** 本轮 standalone delta target 修复 SHALL NOT 改变该路径的 `target_weight`
