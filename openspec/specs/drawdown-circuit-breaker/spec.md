# drawdown-circuit-breaker Specification

## Purpose
~~回撤熔断机制 - 组合级风控，当组合回撤超过阈值时暂停所有新开仓，回撤恢复后解除。~~

**SUPERSEDED** by `risk-budget-sizing` — 原有的二元熔断机制（触发阈值/恢复阈值）已被渐进式回撤缩放完全替代。新系统在 10%/15%/20% 三档渐进降低风险预算，25% 红线停止交易。

## Requirements

_All requirements removed. See `risk-budget-sizing` spec for replacement._

- ~~回撤熔断暂停开仓~~ → replaced by `risk-budget-sizing > 渐进式回撤缩放`
- ~~回撤熔断计数器~~ → replaced by `risk-budget-sizing > 风险预算可观测性`（`dd_scale_08_count`、`dd_scale_06_count`、`dd_fixed_03_count`、`dd_stop_count`、`dd_stop_block_count`）
- ~~前端回撤熔断配置~~ → replaced by `risk-budget-sizing > 前端风险预算配置`
