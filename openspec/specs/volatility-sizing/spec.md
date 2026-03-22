# volatility-sizing Specification

## Purpose
~~波动率调仓机制 - 基于 ATR 反比的仓位调整，波动率越高仓位越小，实现风险均衡化。~~

**SUPERSEDED** by `risk-budget-sizing` — 原有的 ATR 反比缩放公式（`risk_amount / (atr/close)` 加 30%-200% 上下限）已被风险预算公式（`risk_amount / (k * ATR)`）完全替代。Market filter 的 `trend_multiplier` 动态逻辑已迁移至 `risk-budget-sizing > 组合风险预算计算`。

## Requirements

### Requirement: Volatility sizing capability remains retired

系统 SHALL 将旧的 volatility sizing capability 视为已退役能力，并将其 active requirement 全部指向 `risk-budget-sizing` 的对应章节。

#### Scenario: 查询旧 ATR 反比调仓要求
- **WHEN** 维护者查阅 volatility sizing 主规格
- **THEN** 文档 SHALL 指向 `risk-budget-sizing > ATR 定仓公式` 作为 replacement

#### Scenario: 查询旧配置与可观测性要求
- **WHEN** 维护者查阅旧的前端配置或可观测性要求
- **THEN** 文档 SHALL 指向 `risk-budget-sizing` 中对应的前端和 observability 章节
