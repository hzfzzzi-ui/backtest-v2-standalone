## REMOVED Requirements

### Requirement: 回撤熔断暂停开仓
**REMOVED** — 被 `risk-budget-sizing` 的渐进式回撤缩放完全替代。

原有的二元熔断机制（`enable_drawdown_breaker`、触发阈值 15%、恢复阈值 10%）全部移除。新系统在 10%/15%/20% 三档渐进降低风险预算，25% 红线停止交易，不再有"恢复阈值"概念。

### Requirement: 回撤熔断计数器
**REMOVED** — 原有 `drawdown_breaker_block_count`、`drawdown_breaker_trigger_count`、`drawdown_breaker_recover_count` 三个计数器移除。替代为 risk-budget-sizing 的分档计数器（`dd_scale_08_count`、`dd_scale_06_count`、`dd_fixed_03_count`、`dd_stop_count`、`dd_stop_block_count`）。

### Requirement: 前端回撤熔断配置
**REMOVED** — "回撤熔断" checkbox 及触发/恢复阈值输入从前端移除。替代 UI 为 risk-budget-sizing 的回撤缩放参数组。
