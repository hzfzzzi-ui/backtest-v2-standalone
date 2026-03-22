# drawdown-circuit-breaker Specification

## Purpose
~~回撤熔断机制 - 组合级风控，当组合回撤超过阈值时暂停所有新开仓，回撤恢复后解除。~~

**SUPERSEDED** by `risk-budget-sizing` — 原有的二元熔断机制（触发阈值/恢复阈值）已被渐进式回撤缩放完全替代。新系统在 10%/15%/20% 三档渐进降低风险预算，25% 红线停止交易。

## Requirements

### Requirement: Drawdown circuit breaker capability remains retired

系统 SHALL 将旧的 drawdown circuit breaker 视为已退役 capability，并将所有 active requirement 迁移到 `risk-budget-sizing`。

#### Scenario: 查询主规格
- **WHEN** 维护者检查 drawdown circuit breaker 主规格
- **THEN** 文档 SHALL 指向 `risk-budget-sizing` 作为唯一 active replacement

#### Scenario: 检查旧需求去向
- **WHEN** 维护者查阅旧的暂停开仓、计数器或前端配置要求
- **THEN** 文档 SHALL 说明这些要求已分别迁移到 `risk-budget-sizing` 的对应章节
