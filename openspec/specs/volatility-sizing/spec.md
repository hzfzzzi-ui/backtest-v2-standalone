# volatility-sizing Specification

## Purpose
~~波动率调仓机制 - 基于 ATR 反比的仓位调整，波动率越高仓位越小，实现风险均衡化。~~

**SUPERSEDED** by `risk-budget-sizing` — 原有的 ATR 反比缩放公式（`risk_amount / (atr/close)` 加 30%-200% 上下限）已被风险预算公式（`risk_amount / (k * ATR)`）完全替代。Market filter 的 `trend_multiplier` 动态逻辑已迁移至 `risk-budget-sizing > 组合风险预算计算`。

## Requirements

_All requirements removed. See `risk-budget-sizing` spec for replacement._

- ~~ATR 反比调仓~~ → replaced by `risk-budget-sizing > ATR 定仓公式`
- ~~波动率调仓可观测性~~ → replaced by `risk-budget-sizing > 风险预算可观测性`
- ~~前端波动率调仓配置~~ → replaced by `risk-budget-sizing > 前端风险预算配置`
